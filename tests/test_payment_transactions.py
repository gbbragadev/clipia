import asyncio
from types import SimpleNamespace

import pytest
import stripe
from sqlalchemy import func, select

from app.db import models
from app.db.models import CreditPurchase, User
from app.payments.service import (
    create_checkout,
    create_checkout_stripe,
    process_webhook,
    process_webhook_stripe,
)


def _paid_event(
    purchase: CreditPurchase,
    *,
    event_id: str = "evt_paid_1",
    session_id: str | None = None,
    payment_intent: str = "pi_test_1",
) -> dict:
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": session_id or purchase.mp_preference_id,
                "payment_status": "paid",
                "client_reference_id": str(purchase.id),
                "metadata": {"purchase_id": str(purchase.id)},
                "amount_total": purchase.price_brl,
                "currency": "brl",
                "payment_intent": payment_intent,
            }
        },
    }


def _refund_event(
    purchase: CreditPurchase,
    *,
    event_id: str = "evt_refund_1",
    payment_intent: str = "pi_test_1",
    amount_refunded: int | None = None,
) -> dict:
    return {
        "id": event_id,
        "type": "charge.refunded",
        "data": {
            "object": {
                "id": "ch_test_1",
                "payment_intent": payment_intent,
                "amount": purchase.price_brl,
                "amount_refunded": purchase.price_brl if amount_refunded is None else amount_refunded,
                "currency": "brl",
                "refunded": True,
            }
        },
    }


def _patch_payment_intent(monkeypatch, purchase: CreditPurchase, payment_intent: str = "pi_test_1") -> None:
    monkeypatch.setattr(
        stripe.PaymentIntent,
        "retrieve",
        staticmethod(lambda pi: {"id": pi, "metadata": {"purchase_id": str(purchase.id)}}),
    )


def _mp_payment(purchase: CreditPurchase, status: str, payment_id: str = "123") -> dict:
    return {
        "id": payment_id,
        "status": status,
        "external_reference": str(purchase.id),
        "transaction_amount": purchase.price_brl / 100,
        "currency_id": "BRL",
        "preference_id": purchase.mp_preference_id,
    }


def _patch_mp(monkeypatch, payload_by_id: dict[str, dict]) -> None:
    class _Payment:
        @staticmethod
        def get(payment_id):
            return {"status": 200, "response": payload_by_id[str(payment_id)]}

    class _Sdk:
        @staticmethod
        def payment():
            return _Payment()

    monkeypatch.setattr("app.payments.service._get_sdk", lambda: _Sdk())


@pytest.mark.asyncio
async def test_two_concurrent_purchases_for_same_user_preserve_exact_sum(
    test_db, db_session, purchase_factory, verified_user
):
    first = await purchase_factory(provider="stripe", mp_preference_id="cs_first")
    second = await purchase_factory(provider="stripe", mp_preference_id="cs_second")

    async def apply(event):
        async with test_db["session_factory"]() as session:
            return await process_webhook_stripe(event, session)

    changed = await asyncio.gather(
        apply(_paid_event(first, event_id="evt_first", payment_intent="pi_first")),
        apply(_paid_event(second, event_id="evt_second", payment_intent="pi_second")),
    )

    db_session.expire_all()
    assert changed == [True, True]
    assert (await db_session.get(User, verified_user.id)).credits == 25


@pytest.mark.asyncio
async def test_stripe_refund_before_paid_is_terminal_and_late_paid_does_not_credit(
    db_session, purchase_factory, verified_user, monkeypatch
):
    purchase = await purchase_factory(provider="stripe")
    initial = (await db_session.get(User, verified_user.id)).credits
    _patch_payment_intent(monkeypatch, purchase)

    refunded = await process_webhook_stripe(_refund_event(purchase), db_session)
    paid = await process_webhook_stripe(_paid_event(purchase), db_session)

    db_session.expire_all()
    refreshed = await db_session.get(CreditPurchase, purchase.id)
    assert [refunded, paid] == [False, False]
    assert refreshed.status == "refunded"
    assert refreshed.mp_payment_id == "pi_test_1"
    assert (await db_session.get(User, verified_user.id)).credits == initial


@pytest.mark.asyncio
async def test_concurrent_stripe_paid_and_refund_converge_to_refunded_and_initial_balance(
    test_db, db_session, purchase_factory, verified_user, monkeypatch
):
    purchase = await purchase_factory(provider="stripe")
    initial = (await db_session.get(User, verified_user.id)).credits
    _patch_payment_intent(monkeypatch, purchase)

    async def apply(event):
        async with test_db["session_factory"]() as session:
            return await process_webhook_stripe(event, session)

    await asyncio.gather(apply(_paid_event(purchase)), apply(_refund_event(purchase)))

    db_session.expire_all()
    assert (await db_session.get(CreditPurchase, purchase.id)).status == "refunded"
    assert (await db_session.get(User, verified_user.id)).credits == initial


@pytest.mark.asyncio
@pytest.mark.parametrize("mismatch", ["amount", "currency", "session", "provider"])
async def test_stripe_paid_rejects_financial_identity_mismatches_without_claim(
    db_session, purchase_factory, verified_user, mismatch
):
    provider = "mercadopago" if mismatch == "provider" else "stripe"
    purchase = await purchase_factory(provider=provider, mp_preference_id="cs_expected")
    event = _paid_event(purchase)
    obj = event["data"]["object"]
    if mismatch == "amount":
        obj["amount_total"] += 1
    elif mismatch == "currency":
        obj["currency"] = "usd"
    elif mismatch == "session":
        obj["id"] = "cs_wrong"

    assert await process_webhook_stripe(event, db_session) is False
    event_model = getattr(models, "ProcessedPaymentEvent", None)
    assert event_model is not None
    assert await db_session.scalar(select(func.count()).select_from(event_model)) == 0
    db_session.expire_all()
    assert (await db_session.get(User, verified_user.id)).credits == 5


@pytest.mark.asyncio
async def test_stripe_partial_refund_is_rejected_without_debit_or_claim(
    db_session, purchase_factory, verified_user, monkeypatch
):
    purchase = await purchase_factory(provider="stripe", status="approved", mp_payment_id="pi_test_1")
    user = await db_session.get(User, verified_user.id)
    user.credits += purchase.credits_amount
    await db_session.commit()
    before = user.credits
    _patch_payment_intent(monkeypatch, purchase)

    changed = await process_webhook_stripe(_refund_event(purchase, amount_refunded=purchase.price_brl - 1), db_session)

    assert changed is False
    db_session.expire_all()
    assert (await db_session.get(CreditPurchase, purchase.id)).status == "approved"
    assert (await db_session.get(User, verified_user.id)).credits == before
    event_model = getattr(models, "ProcessedPaymentEvent", None)
    assert event_model is not None
    assert await db_session.scalar(select(func.count()).select_from(event_model)) == 0


@pytest.mark.asyncio
async def test_same_signed_stripe_event_id_is_claimed_once(db_session, purchase_factory, verified_user):
    purchase = await purchase_factory(provider="stripe")
    event = _paid_event(purchase, event_id="evt_same")

    assert await process_webhook_stripe(event, db_session) is True
    assert await process_webhook_stripe(event, db_session) is False

    event_model = getattr(models, "ProcessedPaymentEvent", None)
    assert event_model is not None
    assert await db_session.scalar(select(func.count()).select_from(event_model)) == 1
    db_session.expire_all()
    assert (await db_session.get(User, verified_user.id)).credits == 15


@pytest.mark.asyncio
async def test_mp_replay_and_later_refund_each_apply_once(db_session, purchase_factory, verified_user, monkeypatch):
    purchase = await purchase_factory()
    payloads = {"123": _mp_payment(purchase, "approved")}
    _patch_mp(monkeypatch, payloads)

    first = await process_webhook("123", db_session)
    replay = await process_webhook("123", db_session)
    payloads["123"] = _mp_payment(purchase, "refunded")
    refund = await process_webhook("123", db_session)
    refund_replay = await process_webhook("123", db_session)

    assert [first, replay, refund, refund_replay] == [True, False, True, False]
    db_session.expire_all()
    assert (await db_session.get(CreditPurchase, purchase.id)).status == "refunded"
    assert (await db_session.get(User, verified_user.id)).credits == 5
    event_model = getattr(models, "ProcessedPaymentEvent", None)
    assert event_model is not None
    assert await db_session.scalar(select(func.count()).select_from(event_model)) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("mismatch", ["amount", "currency", "provider"])
async def test_mp_rejects_authoritative_mismatches_without_claim(
    db_session, purchase_factory, verified_user, monkeypatch, mismatch
):
    provider = "stripe" if mismatch == "provider" else "mercadopago"
    purchase = await purchase_factory(provider=provider)
    payment = _mp_payment(purchase, "approved")
    if mismatch == "amount":
        payment["transaction_amount"] += 0.01
    elif mismatch == "currency":
        payment["currency_id"] = "USD"
    _patch_mp(monkeypatch, {"123": payment})

    assert await process_webhook("123", db_session) is False
    event_model = getattr(models, "ProcessedPaymentEvent", None)
    assert event_model is not None
    assert await db_session.scalar(select(func.count()).select_from(event_model)) == 0
    db_session.expire_all()
    assert (await db_session.get(User, verified_user.id)).credits == 5


@pytest.mark.asyncio
async def test_checkout_snapshots_bonus_for_both_providers_and_stripe_uses_snapshot_for_refund(
    db_session, verified_user, monkeypatch
):
    monkeypatch.setattr("app.payments.service.settings.PURCHASE_BONUS_PERCENT", 20)

    class _Preference:
        @staticmethod
        def create(_payload):
            return {"status": 201, "response": {"id": "pref_snap", "init_point": "https://mp.test"}}

    class _Sdk:
        @staticmethod
        def preference():
            return _Preference()

    monkeypatch.setattr("app.payments.service._get_sdk", lambda: _Sdk())
    await create_checkout(verified_user, "starter", db_session)

    captured: dict = {}

    def create_session(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id="cs_snap", url="https://stripe.test")

    monkeypatch.setattr("app.payments.service.settings.STRIPE_SECRET_KEY", "sk_test")
    monkeypatch.setattr(stripe.checkout.Session, "create", staticmethod(create_session))
    _, stripe_purchase_id = await create_checkout_stripe(verified_user, "starter", db_session)

    stripe_purchase = await db_session.get(CreditPurchase, stripe_purchase_id)
    purchases = (await db_session.scalars(select(CreditPurchase))).all()
    assert [purchase.bonus_credits for purchase in purchases] == [2, 2]
    assert captured["payment_intent_data"]["metadata"]["purchase_id"] == str(stripe_purchase_id)

    monkeypatch.setattr("app.payments.service.settings.PURCHASE_BONUS_PERCENT", 0)
    assert await process_webhook_stripe(_paid_event(stripe_purchase), db_session) is True
    db_session.expire_all()
    assert (await db_session.get(User, verified_user.id)).credits == 17

    monkeypatch.setattr("app.payments.service.settings.PURCHASE_BONUS_PERCENT", 99)
    stripe_purchase = await db_session.get(CreditPurchase, stripe_purchase_id)
    _patch_payment_intent(monkeypatch, stripe_purchase)
    assert await process_webhook_stripe(_refund_event(stripe_purchase), db_session) is True
    db_session.expire_all()
    assert (await db_session.get(User, verified_user.id)).credits == 5


def test_processed_payment_event_model_has_financially_minimal_schema():
    event_model = getattr(models, "ProcessedPaymentEvent", None)
    assert event_model is not None
    table = event_model.__table__
    assert {column.name for column in table.primary_key.columns} == {"provider", "event_key"}
    assert {column.name for column in table.columns} == {
        "provider",
        "event_key",
        "purchase_id",
        "event_type",
        "processed_at",
    }
    assert {fk.target_fullname for fk in table.c.purchase_id.foreign_keys} == {"credit_purchases.id"}
    assert any(index.columns.keys() == ["purchase_id"] and not index.unique for index in table.indexes)
