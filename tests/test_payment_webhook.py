import hashlib
import hmac
from datetime import datetime

import pytest

from app.db.models import CreditPurchase, User


@pytest.mark.asyncio
async def test_checkout_creates_pending_purchase(client, db_session, verified_user, auth_headers, monkeypatch):
    class _Sdk:
        class preference:
            @staticmethod
            def create(_payload):
                return {
                    "status": 201,
                    "response": {"id": "pref_123", "init_point": "https://checkout.example/test"},
                }

    monkeypatch.setattr("app.payments.service._get_sdk", lambda: _Sdk())

    response = await client.post(
        "/api/v1/credits/checkout",
        headers=auth_headers(verified_user),
        json={"package": "starter"},
    )

    assert response.status_code == 200, "Checkout should succeed for valid packages."
    purchase = await db_session.get(CreditPurchase, response.json()["purchase_id"])
    assert purchase is not None, "Checkout should persist a credit purchase."
    assert purchase.status == "pending", "New purchases should start in pending status."
    assert purchase.credits_amount == 10, "Starter package should persist the expected credit amount."


@pytest.mark.asyncio
async def test_checkout_rejects_invalid_package(client, verified_user, auth_headers):
    response = await client.post(
        "/api/v1/credits/checkout",
        headers=auth_headers(verified_user),
        json={"package": "bad-package"},
    )
    assert response.status_code == 400, "Invalid credit packages must be rejected."


@pytest.mark.asyncio
async def test_webhook_rejects_missing_or_invalid_signature(client, monkeypatch):
    monkeypatch.setattr("app.payments.routes.settings.MP_WEBHOOK_SECRET", "secret")
    payload = {"action": "payment.updated", "data": {"id": "123"}}

    missing = await client.post("/api/v1/webhooks/mercadopago", json=payload)
    invalid = await client.post(
        "/api/v1/webhooks/mercadopago",
        json=payload,
        headers={"x-signature": "ts=1,v1=bad", "x-request-id": "req-1"},
    )

    assert missing.json()["status"] == "invalid_signature", "Webhook without signature headers must be rejected."
    assert invalid.json()["status"] == "invalid_signature", "Webhook with an invalid signature must be rejected."


@pytest.mark.asyncio
async def test_webhook_with_valid_signature_credits_purchase(client, db_session, purchase_factory, verified_user, monkeypatch):
    purchase = await purchase_factory(package_name="popular")
    monkeypatch.setattr("app.payments.routes.settings.MP_WEBHOOK_SECRET", "secret")

    class _Sdk:
        class payment:
            @staticmethod
            def get(_payment_id):
                return {"response": {"status": "approved", "external_reference": str(purchase.id)}}

    monkeypatch.setattr("app.payments.service._get_sdk", lambda: _Sdk())

    ts = str(int(datetime.now().timestamp()))
    manifest = f"id:123;request-id:req-1;ts:{ts};"
    signature = hmac.new(b"secret", manifest.encode(), hashlib.sha256).hexdigest()

    response = await client.post(
        "/api/v1/webhooks/mercadopago",
        json={"action": "payment.updated", "data": {"id": "123"}},
        headers={"x-signature": f"ts={ts},v1={signature}", "x-request-id": "req-1"},
    )

    assert response.json()["status"] == "credited", "Approved signed webhooks should credit the purchase."
    refreshed_purchase = await db_session.get(CreditPurchase, purchase.id)
    refreshed_user = await db_session.get(User, verified_user.id)
    assert refreshed_purchase.status == "approved", "Signed approved webhooks should mark purchases approved."
    assert refreshed_purchase.mp_payment_id == "123", "Webhook should persist the payment id."
    assert refreshed_user.credits == 35, "Popular package webhook should credit 30 credits exactly once."


@pytest.mark.asyncio
async def test_webhook_ignores_irrelevant_actions_and_missing_payment_id(client):
    ignored = await client.post("/api/v1/webhooks/mercadopago", json={"action": "merchant_order"})
    missing = await client.post("/api/v1/webhooks/mercadopago", json={"action": "payment.updated"})

    assert ignored.json()["status"] == "ignored", "Irrelevant webhook actions should be ignored."
    assert missing.json()["status"] == "no_payment_id", "Payment webhooks without an id should be reported clearly."
