import asyncio
from types import SimpleNamespace

import pytest
import stripe
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.db import models
from app.db.models import AnalyticsEvent, CreditPurchase, User
from app.payments.service import (
    create_checkout,
    create_checkout_stripe,
    process_webhook,
    process_webhook_stripe,
)
from app.payments.snapshot import build_snapshot_metadata


def _paid_event(
    purchase: CreditPurchase,
    *,
    event_id: str = "evt_paid_1",
    session_id: str | None = None,
    payment_intent: str = "pi_test_1",
) -> dict:
    metadata = (
        build_snapshot_metadata(purchase) if purchase.snapshot_version == 1 else {"purchase_id": str(purchase.id)}
    )
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": session_id or purchase.mp_preference_id,
                "payment_status": "paid",
                "client_reference_id": str(purchase.id),
                "metadata": metadata,
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
    metadata = (
        build_snapshot_metadata(purchase) if purchase.snapshot_version == 1 else {"purchase_id": str(purchase.id)}
    )
    monkeypatch.setattr(
        stripe.PaymentIntent,
        "retrieve",
        staticmethod(lambda pi: {"id": pi, "metadata": metadata}),
    )


def _mp_payment(purchase: CreditPurchase, status: str, payment_id: str = "123") -> dict:
    payment = {
        "id": payment_id,
        "status": status,
        "external_reference": str(purchase.id),
        "transaction_amount": purchase.price_brl / 100,
        "currency_id": "BRL",
        "preference_id": purchase.mp_preference_id,
    }
    if purchase.snapshot_version == 1:
        payment["metadata"] = build_snapshot_metadata(purchase)
    return payment


def _patch_mp(monkeypatch, payload_by_id: dict[str, dict], merchant_orders: dict[str, dict] | None = None) -> None:
    class _Payment:
        @staticmethod
        def get(payment_id):
            return {"status": 200, "response": payload_by_id[str(payment_id)]}

    class _Sdk:
        @staticmethod
        def payment():
            return _Payment()

        @staticmethod
        def merchant_order():
            class _MerchantOrder:
                @staticmethod
                def get(order_id):
                    if merchant_orders is None:
                        raise AssertionError("merchant order lookup was not expected")
                    return {"status": 200, "response": merchant_orders[str(order_id)]}

            return _MerchantOrder()

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
    assert [result.applied for result in changed] == [True, True]
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
    assert [refunded.applied, paid.applied] == [True, False]
    assert refreshed.status == "refunded"
    assert refreshed.refunded_at is not None
    assert refreshed.mp_payment_id == "pi_test_1"
    assert (await db_session.get(User, verified_user.id)).credits == initial


@pytest.mark.asyncio
async def test_refund_reports_only_the_balance_delta_actually_applied(
    db_session,
    purchase_factory,
    verified_user,
    monkeypatch,
):
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)
    purchase = await purchase_factory(
        provider="stripe",
        status="approved",
        payment_state="paid",
        mp_payment_id="pi_partial_refund",
    )
    user = await db_session.get(User, verified_user.id)
    user.credits = 3
    await db_session.commit()
    _patch_payment_intent(monkeypatch, purchase, "pi_partial_refund")

    result = await process_webhook_stripe(
        _refund_event(purchase, payment_intent="pi_partial_refund"),
        db_session,
    )

    db_session.expire_all()
    assert (result.applied, result.balance_delta, result.state) == (True, -3, "refunded")
    assert (await db_session.get(User, verified_user.id)).credits == 0
    credit_event = await db_session.scalar(
        select(AnalyticsEvent).where(
            AnalyticsEvent.event_name == "credit_balance_changed",
            AnalyticsEvent.user_id == verified_user.id,
        )
    )
    assert credit_event is not None
    assert credit_event.properties == {"reason": "refund", "delta": -3}


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

    assert (await process_webhook_stripe(event, db_session)).applied is False
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

    assert changed.applied is False
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

    assert (await process_webhook_stripe(event, db_session)).applied is True
    assert (await process_webhook_stripe(event, db_session)).applied is False

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

    assert [result.applied for result in (first, replay, refund, refund_replay)] == [
        True,
        False,
        True,
        False,
    ]
    db_session.expire_all()
    assert (await db_session.get(CreditPurchase, purchase.id)).status == "refunded"
    assert (await db_session.get(User, verified_user.id)).credits == 5
    event_model = getattr(models, "ProcessedPaymentEvent", None)
    assert event_model is not None
    assert await db_session.scalar(select(func.count()).select_from(event_model)) == 2


@pytest.mark.asyncio
async def test_legacy_mp_missing_preference_is_accepted_only_with_exact_merchant_order_proof(
    db_session, purchase_factory, verified_user, monkeypatch
):
    purchase = await purchase_factory()
    payment = _mp_payment(purchase, "approved")
    payment.pop("preference_id")
    payment["order"] = {"id": "merchant-order-456"}
    _patch_mp(
        monkeypatch,
        {"123": payment},
        {
            "merchant-order-456": {
                "id": "merchant-order-456",
                "preference_id": purchase.mp_preference_id,
                "payments": [{"id": "123", "status": "approved"}],
            }
        },
    )

    assert (await process_webhook("123", db_session)).applied is True
    db_session.expire_all()
    assert (await db_session.get(CreditPurchase, purchase.id)).status == "approved"
    assert (await db_session.get(User, verified_user.id)).credits == 15


@pytest.mark.asyncio
@pytest.mark.parametrize("mismatch", ["missing_order", "wrong_preference", "missing_payment"])
async def test_legacy_mp_ambiguous_identity_is_rejected_without_claim(
    db_session, purchase_factory, verified_user, monkeypatch, mismatch
):
    purchase = await purchase_factory()
    payment = _mp_payment(purchase, "approved")
    payment.pop("preference_id")
    merchant_orders = None
    if mismatch != "missing_order":
        payment["order"] = {"id": "merchant-order-456"}
        merchant_orders = {
            "merchant-order-456": {
                "id": "merchant-order-456",
                "preference_id": "pref_wrong" if mismatch == "wrong_preference" else purchase.mp_preference_id,
                "payments": [] if mismatch == "missing_payment" else [{"id": "123"}],
            }
        }
    _patch_mp(monkeypatch, {"123": payment}, merchant_orders)

    result = await process_webhook("123", db_session)
    assert result.applied is False
    assert await db_session.scalar(select(func.count()).select_from(models.ProcessedPaymentEvent)) == 0
    db_session.expire_all()
    assert (await db_session.get(CreditPurchase, purchase.id)).status == "pending"
    assert (await db_session.get(User, verified_user.id)).credits == 5


@pytest.mark.asyncio
async def test_unrelated_integrity_error_without_event_claim_is_propagated(
    test_db, db_session, purchase_factory, monkeypatch
):
    purchase = await purchase_factory(provider="stripe")

    async def fail_flush(*_args, **_kwargs):
        raise IntegrityError("INSERT unrelated_table", {}, RuntimeError("unrelated constraint"))

    monkeypatch.setattr(db_session, "flush", fail_flush)

    with pytest.raises(IntegrityError):
        await process_webhook_stripe(_paid_event(purchase), db_session)

    event_model = getattr(models, "ProcessedPaymentEvent")
    async with test_db["session_factory"]() as verification_session:
        assert await verification_session.scalar(select(func.count()).select_from(event_model)) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_status", ["cancelled", "rejected"])
async def test_mp_failed_payment_terminalizes_without_binding_payment_id(
    db_session, purchase_factory, verified_user, monkeypatch, provider_status
):
    purchase = await purchase_factory()
    _patch_mp(monkeypatch, {"123": _mp_payment(purchase, provider_status)})

    result = await process_webhook("123", db_session)
    assert (result.applied, result.balance_delta, result.state) == (True, 0, "void")
    db_session.expire_all()
    refreshed = await db_session.get(CreditPurchase, purchase.id)
    assert refreshed.status == "pending"
    assert refreshed.payment_state == "void"
    assert refreshed.mp_payment_id is None
    assert (await db_session.get(User, verified_user.id)).credits == 5
    event_model = getattr(models, "ProcessedPaymentEvent")
    assert await db_session.scalar(select(func.count()).select_from(event_model)) == 1


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

    assert (await process_webhook("123", db_session)).applied is False
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
        def create(_payload, request_options=None):
            preference_id = "202809963-a2201f8d-11cb-443f-adf6-de5a42eed67d"
            return {
                "status": 201,
                "response": {
                    "id": preference_id,
                    "init_point": f"https://www.mercadopago.com/mla/checkout/start?pref_id={preference_id}",
                },
            }

    class _Sdk:
        @staticmethod
        def preference():
            return _Preference()

    monkeypatch.setattr("app.payments.service._get_sdk", lambda: _Sdk())
    await create_checkout(verified_user, "starter", db_session)

    captured: dict = {}

    def create_session(**kwargs):
        captured.update(kwargs)
        session_id = "cs_test_a12345678"
        return SimpleNamespace(
            id=session_id,
            url=f"https://checkout.stripe.com/c/pay/{session_id}",
        )

    monkeypatch.setattr("app.payments.service.settings.STRIPE_SECRET_KEY", "sk_test")
    monkeypatch.setattr(stripe.checkout.Session, "create", staticmethod(create_session))
    _, stripe_purchase_id = await create_checkout_stripe(verified_user, "starter", db_session)

    stripe_purchase = await db_session.get(CreditPurchase, stripe_purchase_id)
    purchases = (await db_session.scalars(select(CreditPurchase))).all()
    assert [purchase.bonus_credits for purchase in purchases] == [2, 2]
    assert captured["payment_intent_data"]["metadata"]["purchase_id"] == str(stripe_purchase_id)

    monkeypatch.setattr("app.payments.service.settings.PURCHASE_BONUS_PERCENT", 0)
    assert (await process_webhook_stripe(_paid_event(stripe_purchase), db_session)).applied is True
    db_session.expire_all()
    assert (await db_session.get(User, verified_user.id)).credits == 17

    monkeypatch.setattr("app.payments.service.settings.PURCHASE_BONUS_PERCENT", 99)
    stripe_purchase = await db_session.get(CreditPurchase, stripe_purchase_id)
    _patch_payment_intent(monkeypatch, stripe_purchase)
    assert (await process_webhook_stripe(_refund_event(stripe_purchase), db_session)).applied is True
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


@pytest.mark.asyncio
async def test_void_purchase_can_later_be_paid_but_refunded_purchase_cannot(
    db_session, purchase_factory, verified_user
):
    void_purchase = await purchase_factory(
        provider="stripe",
        mp_preference_id="cs_void",
        status="pending",
        payment_state="void",
    )
    refunded_purchase = await purchase_factory(
        provider="stripe",
        mp_preference_id="cs_refunded",
        status="refunded",
        payment_state="refunded",
    )

    void_changed = await process_webhook_stripe(
        _paid_event(void_purchase, event_id="evt_void_paid", payment_intent="pi_void"),
        db_session,
    )
    refunded_changed = await process_webhook_stripe(
        _paid_event(refunded_purchase, event_id="evt_refunded_paid", payment_intent="pi_refunded"),
        db_session,
    )

    db_session.expire_all()
    assert [void_changed.applied, refunded_changed.applied] == [True, False]
    assert (await db_session.get(CreditPurchase, void_purchase.id)).payment_state == "paid"
    assert (await db_session.get(CreditPurchase, refunded_purchase.id)).payment_state == "refunded"
    assert (await db_session.get(User, verified_user.id)).credits == 15


@pytest.mark.asyncio
@pytest.mark.parametrize("event_type", ["checkout.session.expired", "checkout.session.async_payment_failed"])
async def test_stripe_failed_checkout_terminalizes_without_binding_payment_intent(
    db_session, purchase_factory, verified_user, event_type
):
    purchase = await purchase_factory(provider="stripe", mp_preference_id="cs_failed")
    event = _paid_event(purchase, event_id=f"evt_{event_type}", payment_intent="pi_must_not_bind")
    event["type"] = event_type
    event["data"]["object"]["payment_status"] = "unpaid"

    result = await process_webhook_stripe(event, db_session)
    assert (result.applied, result.balance_delta, result.state) == (True, 0, "void")

    db_session.expire_all()
    refreshed = await db_session.get(CreditPurchase, purchase.id)
    assert refreshed.status == "pending"
    assert refreshed.payment_state == "void"
    assert refreshed.mp_payment_id is None
    assert (await db_session.get(User, verified_user.id)).credits == 5
    assert await db_session.scalar(select(func.count()).select_from(models.ProcessedPaymentEvent)) == 1


@pytest.mark.asyncio
async def test_stripe_refund_rejects_payment_intent_retrieve_without_exact_id(
    db_session, purchase_factory, verified_user, monkeypatch
):
    purchase = await purchase_factory(provider="stripe", status="approved", mp_payment_id="pi_expected")
    user = await db_session.get(User, verified_user.id)
    user.credits += purchase.credits_amount
    await db_session.commit()
    monkeypatch.setattr(
        stripe.PaymentIntent,
        "retrieve",
        staticmethod(lambda _pi: {"metadata": {"purchase_id": str(purchase.id)}}),
    )

    assert (
        await process_webhook_stripe(_refund_event(purchase, payment_intent="pi_expected"), db_session)
    ).applied is False
    assert await db_session.scalar(select(func.count()).select_from(models.ProcessedPaymentEvent)) == 0
    db_session.expire_all()
    assert (await db_session.get(CreditPurchase, purchase.id)).status == "approved"
    assert (await db_session.get(User, verified_user.id)).credits == 15


@pytest.mark.asyncio
async def test_provider_payment_identity_cannot_credit_two_purchases(db_session, purchase_factory, verified_user):
    first = await purchase_factory(provider="stripe", mp_preference_id="cs_identity_first")
    second = await purchase_factory(provider="stripe", mp_preference_id="cs_identity_second")

    first_result = await process_webhook_stripe(
        _paid_event(first, event_id="evt_identity_first", payment_intent="pi_shared"), db_session
    )
    second_result = await process_webhook_stripe(
        _paid_event(second, event_id="evt_identity_second", payment_intent="pi_shared"), db_session
    )

    db_session.expire_all()
    assert [first_result.applied, second_result.applied] == [True, False]
    assert (await db_session.get(CreditPurchase, first.id)).status == "approved"
    assert (await db_session.get(CreditPurchase, second.id)).status == "pending"
    assert (await db_session.get(User, verified_user.id)).credits == 15


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tampered_field",
    ["provider", "package", "credits", "bonus", "amount_cents", "currency", "snapshot_version", "snapshot_hash"],
)
async def test_new_stripe_purchase_requires_exact_frozen_snapshot_metadata(
    db_session, purchase_factory, verified_user, tampered_field
):
    purchase = await purchase_factory(
        provider="stripe",
        mp_preference_id=f"cs_snapshot_{tampered_field}",
        snapshot=True,
    )
    event = _paid_event(purchase, event_id=f"evt_snapshot_{tampered_field}")
    event["data"]["object"]["metadata"][tampered_field] += "-tampered"

    assert (await process_webhook_stripe(event, db_session)).applied is False
    assert await db_session.scalar(select(func.count()).select_from(models.ProcessedPaymentEvent)) == 0
    db_session.expire_all()
    assert (await db_session.get(CreditPurchase, purchase.id)).status == "pending"
    assert (await db_session.get(User, verified_user.id)).credits == 5


@pytest.mark.asyncio
async def test_new_mp_purchase_requires_exact_snapshot_but_ignores_later_catalog_changes(
    db_session, purchase_factory, verified_user, monkeypatch
):
    purchase = await purchase_factory(snapshot=True)
    payment = _mp_payment(purchase, "approved")
    original = dict(__import__("app.payments.service", fromlist=["CREDIT_PACKAGES"]).CREDIT_PACKAGES["starter"])
    monkeypatch.setitem(
        __import__("app.payments.service", fromlist=["CREDIT_PACKAGES"]).CREDIT_PACKAGES,
        "starter",
        {"name": "Changed", "credits": 999, "price_brl": 1},
    )
    _patch_mp(monkeypatch, {"123": payment})

    assert (await process_webhook("123", db_session)).applied is True
    db_session.expire_all()
    assert (await db_session.get(User, verified_user.id)).credits == 5 + original["credits"]


@pytest.mark.asyncio
async def test_new_mp_purchase_missing_snapshot_metadata_is_rejected_without_claim(
    db_session, purchase_factory, verified_user, monkeypatch
):
    purchase = await purchase_factory(snapshot=True)
    payment = _mp_payment(purchase, "approved")
    payment.pop("metadata")
    _patch_mp(monkeypatch, {"123": payment})

    assert (await process_webhook("123", db_session)).applied is False
    assert await db_session.scalar(select(func.count()).select_from(models.ProcessedPaymentEvent)) == 0
    db_session.expire_all()
    assert (await db_session.get(CreditPurchase, purchase.id)).status == "pending"
    assert (await db_session.get(User, verified_user.id)).credits == 5
