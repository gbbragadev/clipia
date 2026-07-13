import time
from types import SimpleNamespace

import pytest
import stripe

from app.db.models import CreditPurchase
from app.payments.service import process_webhook, process_webhook_stripe


def _mp_payment(purchase: CreditPurchase, status: str, payment_id: str) -> dict:
    return {
        "id": payment_id,
        "status": status,
        "external_reference": str(purchase.id),
        "transaction_amount": purchase.price_brl / 100,
        "currency_id": "BRL",
        "preference_id": purchase.mp_preference_id,
    }


def _patch_mp(monkeypatch, payloads: dict[str, dict]) -> None:
    class _Payment:
        @staticmethod
        def get(payment_id):
            return {"status": 200, "response": payloads[str(payment_id)]}

    class _Sdk:
        @staticmethod
        def payment():
            return _Payment()

    monkeypatch.setattr("app.payments.service._get_sdk", lambda: _Sdk())


def _stripe_paid_event(purchase: CreditPurchase, *, event_id: str, payment_intent: str) -> dict:
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": purchase.mp_preference_id,
                "payment_status": "paid",
                "client_reference_id": str(purchase.id),
                "metadata": {"purchase_id": str(purchase.id)},
                "amount_total": purchase.price_brl,
                "currency": "brl",
                "payment_intent": payment_intent,
            }
        },
    }


def _stripe_refund_event(purchase: CreditPurchase, *, event_id: str, payment_intent: str) -> dict:
    return {
        "id": event_id,
        "type": "charge.refunded",
        "data": {
            "object": {
                "id": f"ch_{event_id}",
                "payment_intent": payment_intent,
                "amount": purchase.price_brl,
                "amount_refunded": purchase.price_brl,
                "currency": "brl",
                "refunded": True,
            }
        },
    }


def _stripe_void_event(purchase: CreditPurchase, *, event_id: str) -> dict:
    event = _stripe_paid_event(purchase, event_id=event_id, payment_intent="pi_must_not_bind")
    event["type"] = "checkout.session.expired"
    event["data"]["object"]["payment_status"] = "unpaid"
    return event


@pytest.mark.asyncio
async def test_mp_event_result_distinguishes_paid_replay_refund_and_void(
    db_session,
    purchase_factory,
    monkeypatch,
):
    paid_purchase = await purchase_factory()
    void_purchase = await purchase_factory()
    payloads = {
        "101": _mp_payment(paid_purchase, "approved", "101"),
        "202": _mp_payment(void_purchase, "cancelled", "202"),
    }
    _patch_mp(monkeypatch, payloads)

    paid = await process_webhook("101", db_session)
    replay = await process_webhook("101", db_session)
    payloads["101"] = _mp_payment(paid_purchase, "refunded", "101")
    refunded = await process_webhook("101", db_session)
    voided = await process_webhook("202", db_session)

    assert (paid.applied, paid.balance_delta, paid.state) == (True, 10, "paid")
    assert (replay.applied, replay.balance_delta, replay.state) == (False, 0, "paid")
    assert (refunded.applied, refunded.balance_delta, refunded.state) == (True, -10, "refunded")
    assert (voided.applied, voided.balance_delta, voided.state) == (True, 0, "void")


@pytest.mark.asyncio
async def test_stripe_event_result_distinguishes_paid_replay_refund_and_void(
    db_session,
    purchase_factory,
    monkeypatch,
):
    paid_purchase = await purchase_factory(provider="stripe")
    void_purchase = await purchase_factory(provider="stripe")
    payment_intent = "pi_result_contract"
    monkeypatch.setattr(
        stripe.PaymentIntent,
        "retrieve",
        staticmethod(
            lambda pi: {
                "id": pi,
                "metadata": {"purchase_id": str(paid_purchase.id)},
            }
        ),
    )
    paid_event = _stripe_paid_event(
        paid_purchase,
        event_id="evt_result_paid",
        payment_intent=payment_intent,
    )

    paid = await process_webhook_stripe(paid_event, db_session)
    replay = await process_webhook_stripe(paid_event, db_session)
    refunded = await process_webhook_stripe(
        _stripe_refund_event(
            paid_purchase,
            event_id="evt_result_refund",
            payment_intent=payment_intent,
        ),
        db_session,
    )
    voided = await process_webhook_stripe(
        _stripe_void_event(void_purchase, event_id="evt_result_void"),
        db_session,
    )

    assert (paid.applied, paid.balance_delta, paid.state) == (True, 10, "paid")
    assert (replay.applied, replay.balance_delta, replay.state) == (False, 0, "paid")
    assert (refunded.applied, refunded.balance_delta, refunded.state) == (True, -10, "refunded")
    assert (voided.applied, voided.balance_delta, voided.state) == (True, 0, "void")


@pytest.mark.asyncio
async def test_mp_http_result_never_calls_refund_credited(client, monkeypatch):
    results = iter(
        [
            SimpleNamespace(applied=True, balance_delta=-10, state="refunded"),
            SimpleNamespace(applied=False, balance_delta=0, state="refunded"),
        ]
    )

    async def process_result(*_args, **_kwargs):
        return next(results)

    monkeypatch.setattr("app.payments.routes.settings.MP_WEBHOOK_SECRET", "")
    monkeypatch.setattr("app.payments.routes.process_webhook", process_result)
    body = {"action": "payment.updated", "data": {"id": "101"}}

    refunded = await client.post("/api/v1/webhooks/mercadopago", json=body)
    replay = await client.post("/api/v1/webhooks/mercadopago", json=body)

    assert refunded.json() == {"status": "processed", "state": "refunded", "balance_delta": -10}
    assert replay.json() == {"status": "not_processed", "state": "refunded", "balance_delta": 0}


@pytest.mark.asyncio
async def test_stripe_http_result_never_calls_refund_credited(client, monkeypatch):
    results = iter(
        [
            SimpleNamespace(applied=True, balance_delta=-10, state="refunded"),
            SimpleNamespace(applied=False, balance_delta=0, state="refunded"),
        ]
    )

    async def process_result(*_args, **_kwargs):
        return next(results)

    event = {"id": "evt_refund", "type": "charge.refunded", "data": {"object": {"id": "ch_1"}}}
    monkeypatch.setattr("app.payments.routes.settings.STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setattr(stripe.Webhook, "construct_event", staticmethod(lambda payload, sig, secret: event))
    monkeypatch.setattr("app.payments.routes.process_webhook_stripe", process_result)

    refunded = await client.post(
        "/api/v1/webhooks/stripe",
        json=event,
        headers={"stripe-signature": f"t={int(time.time())},v1=signed"},
    )
    replay = await client.post(
        "/api/v1/webhooks/stripe",
        json=event,
        headers={"stripe-signature": f"t={int(time.time())},v1=signed"},
    )

    assert refunded.json() == {"status": "processed", "state": "refunded", "balance_delta": -10}
    assert replay.json() == {"status": "not_processed", "state": "refunded", "balance_delta": 0}
