import hashlib
import hmac
import json
import time

import pytest
from sqlalchemy import func, select

from app.db.models import CreditPurchase, ProcessedPaymentEvent, User

STRIPE_TOLERANCE_SECONDS = 300


def _payload_bytes(purchase: CreditPurchase, *, event_id: str = "evt_hmac_1") -> bytes:
    event = {
        "id": event_id,
        "object": "event",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": purchase.mp_preference_id,
                "object": "checkout.session",
                "payment_status": "paid",
                "status": "complete",
                "client_reference_id": str(purchase.id),
                "metadata": {"purchase_id": str(purchase.id)},
                "payment_intent": "pi_hmac_1",
                "amount_total": purchase.price_brl,
                "currency": "brl",
            }
        },
    }
    return json.dumps(event, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _stripe_signature(payload: bytes, secret: str, *, timestamp: int | None = None) -> str:
    # stripe-python 15.3.0 has no public generate_header helper. This is the
    # provider-documented signed payload format, while verification still runs
    # through the real stripe.Webhook.construct_event implementation.
    signed_at = int(time.time()) if timestamp is None else timestamp
    signed_payload = f"{signed_at}.".encode() + payload
    digest = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return f"t={signed_at},v1={digest}"


@pytest.mark.asyncio
async def test_real_stripe_sdk_hmac_accepts_identical_raw_body_and_replay_is_idempotent(
    client,
    db_session,
    purchase_factory,
    verified_user,
    monkeypatch,
):
    secret = "whsec_real_hmac_fixture"
    purchase = await purchase_factory(provider="stripe")
    payload = _payload_bytes(purchase)
    monkeypatch.setattr("app.payments.routes.settings.STRIPE_WEBHOOK_SECRET", secret)

    headers = {
        "content-type": "application/json",
        "stripe-signature": _stripe_signature(payload, secret),
    }
    first = await client.post("/api/v1/webhooks/stripe", content=payload, headers=headers)
    replay = await client.post("/api/v1/webhooks/stripe", content=payload, headers=headers)

    assert first.status_code == replay.status_code == 200
    assert first.json() == {"status": "processed", "state": "paid", "balance_delta": 10}
    assert replay.json() == {"status": "not_processed", "state": "paid", "balance_delta": 0}
    db_session.expire_all()
    assert (await db_session.get(User, verified_user.id)).credits == 15
    assert (await db_session.get(CreditPurchase, purchase.id)).payment_state == "paid"
    assert await db_session.scalar(select(func.count()).select_from(ProcessedPaymentEvent)) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["body", "secret"])
async def test_real_stripe_sdk_hmac_rejects_changed_body_or_wrong_secret_without_claim(
    client,
    db_session,
    purchase_factory,
    verified_user,
    monkeypatch,
    mutation,
):
    secret = "whsec_real_hmac_fixture"
    purchase = await purchase_factory(provider="stripe")
    original = _payload_bytes(purchase)
    monkeypatch.setattr("app.payments.routes.settings.STRIPE_WEBHOOK_SECRET", secret)

    if mutation == "body":
        sent = original.replace(str(purchase.price_brl).encode(), b"1", 1)
        signing_secret = secret
    else:
        sent = original
        signing_secret = "whsec_wrong"

    response = await client.post(
        "/api/v1/webhooks/stripe",
        content=sent,
        headers={
            "content-type": "application/json",
            "stripe-signature": _stripe_signature(original, signing_secret),
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "invalid_signature"}
    db_session.expire_all()
    assert (await db_session.get(User, verified_user.id)).credits == 5
    refreshed = await db_session.get(CreditPurchase, purchase.id)
    assert refreshed.status == "pending"
    assert refreshed.payment_state is None
    assert await db_session.scalar(select(func.count()).select_from(ProcessedPaymentEvent)) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "offset",
    [-STRIPE_TOLERANCE_SECONDS - 60, STRIPE_TOLERANCE_SECONDS + 60],
)
async def test_real_stripe_sdk_hmac_rejects_timestamp_outside_tolerance_in_either_direction(
    client,
    db_session,
    purchase_factory,
    verified_user,
    monkeypatch,
    offset,
):
    secret = "whsec_real_hmac_fixture"
    purchase = await purchase_factory(provider="stripe")
    payload = _payload_bytes(purchase, event_id=f"evt_hmac_time_{offset}")
    monkeypatch.setattr("app.payments.routes.settings.STRIPE_WEBHOOK_SECRET", secret)
    timestamp = int(time.time()) + offset

    response = await client.post(
        "/api/v1/webhooks/stripe",
        content=payload,
        headers={
            "content-type": "application/json",
            "stripe-signature": _stripe_signature(payload, secret, timestamp=timestamp),
        },
    )

    assert response.json() == {"status": "invalid_signature"}
    db_session.expire_all()
    assert (await db_session.get(User, verified_user.id)).credits == 5
    assert (await db_session.get(CreditPurchase, purchase.id)).status == "pending"
    assert await db_session.scalar(select(func.count()).select_from(ProcessedPaymentEvent)) == 0
