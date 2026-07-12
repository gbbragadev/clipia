import hashlib
import hmac
from datetime import datetime

import pytest
from sqlalchemy import select

from app.db.models import CreditPurchase, User


def _authoritative_payment(purchase, status: str, payment_id: str = "123"):
    return {
        "id": payment_id,
        "status": status,
        "external_reference": str(purchase.id),
        "transaction_amount": purchase.price_brl / 100,
        "currency_id": "BRL",
        "preference_id": purchase.mp_preference_id,
    }


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
@pytest.mark.parametrize("provider", ["mercadopago", "stripe"])
async def test_checkout_rejects_unverified_user_before_provider_or_purchase(
    client, db_session, unverified_user, auth_headers, monkeypatch, provider
):
    provider_calls = []

    async def unexpected_checkout(*_args, **_kwargs):
        provider_calls.append(provider)
        raise AssertionError("checkout provider must not be called for an unverified user")

    monkeypatch.setattr("app.payments.routes.create_checkout", unexpected_checkout)
    monkeypatch.setattr("app.payments.routes.create_checkout_stripe", unexpected_checkout)

    response = await client.post(
        "/api/v1/credits/checkout",
        headers=auth_headers(unverified_user),
        json={"package": "starter", "provider": provider},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "email_verification_required"
    assert provider_calls == []
    assert await db_session.scalar(select(CreditPurchase)) is None


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
async def test_webhook_with_valid_signature_credits_purchase(
    client, db_session, purchase_factory, verified_user, monkeypatch
):
    purchase = await purchase_factory(package_name="popular")
    monkeypatch.setattr("app.payments.routes.settings.MP_WEBHOOK_SECRET", "secret")

    class _Sdk:
        class payment:
            @staticmethod
            def get(_payment_id):
                return {"response": _authoritative_payment(purchase, "approved")}

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


def _signed_headers():
    ts = str(int(datetime.now().timestamp()))
    manifest = f"id:123;request-id:req-1;ts:{ts};"
    signature = hmac.new(b"secret", manifest.encode(), hashlib.sha256).hexdigest()
    return {"x-signature": f"ts={ts},v1={signature}", "x-request-id": "req-1"}


@pytest.mark.asyncio
async def test_webhook_reverts_credits_on_refund(client, db_session, purchase_factory, verified_user, monkeypatch):
    purchase = await purchase_factory(package_name="popular")
    credits_initial = (await db_session.get(User, verified_user.id)).credits
    monkeypatch.setattr("app.payments.routes.settings.MP_WEBHOOK_SECRET", "secret")

    mp_status = {"value": "approved"}

    class _Sdk:
        class payment:
            @staticmethod
            def get(_payment_id):
                return {"response": _authoritative_payment(purchase, mp_status["value"])}

    monkeypatch.setattr("app.payments.service._get_sdk", lambda: _Sdk())

    # 1) Aprovacao credita
    approved = await client.post(
        "/api/v1/webhooks/mercadopago",
        json={"action": "payment.updated", "data": {"id": "123"}},
        headers=_signed_headers(),
    )
    assert approved.json()["status"] == "credited", "Approval should credit first."

    # 2) Estorno reverte
    mp_status["value"] = "refunded"
    refunded = await client.post(
        "/api/v1/webhooks/mercadopago",
        json={"action": "payment.updated", "data": {"id": "123"}},
        headers=_signed_headers(),
    )
    assert refunded.status_code == 200

    refreshed_purchase = await db_session.get(CreditPurchase, purchase.id)
    refreshed_user = await db_session.get(User, verified_user.id)
    assert refreshed_purchase.status == "refunded", "Refund webhook should mark purchase refunded."
    assert (
        refreshed_user.credits == credits_initial
    ), "Refund must revert the credited amount back to the initial balance."


@pytest.mark.asyncio
async def test_webhook_refund_of_unapproved_purchase_is_noop(
    client, db_session, purchase_factory, verified_user, monkeypatch
):
    purchase = await purchase_factory(package_name="popular")
    purchase.status = "pending"  # nunca foi aprovada
    user = await db_session.get(User, verified_user.id)
    credits_before = user.credits
    await db_session.commit()

    monkeypatch.setattr("app.payments.routes.settings.MP_WEBHOOK_SECRET", "secret")

    class _Sdk:
        class payment:
            @staticmethod
            def get(_payment_id):
                return {"response": _authoritative_payment(purchase, "refunded")}

    monkeypatch.setattr("app.payments.service._get_sdk", lambda: _Sdk())

    response = await client.post(
        "/api/v1/webhooks/mercadopago",
        json={"action": "payment.updated", "data": {"id": "123"}},
        headers=_signed_headers(),
    )

    assert response.json()["status"] == "not_credited", "Refund of a never-approved purchase must be a no-op."
    refreshed_user = await db_session.get(User, verified_user.id)
    assert refreshed_user.credits == credits_before, "No-op refund must not change the balance."


@pytest.mark.asyncio
async def test_webhook_approved_replay_is_idempotent(client, db_session, purchase_factory, verified_user, monkeypatch):
    """Replay do mesmo webhook 'approved' (MP reenvia o mesmo payment) NAO re-credita.

    Espelha test_stripe_webhook_is_idempotent: protege contra duplicacao do lado do
    provedor (retries, reenvio manual no painel) usando o guard de status do _credit_once.
    """
    purchase = await purchase_factory(package_name="popular")  # 30 creditos
    credits_before = (await db_session.get(User, verified_user.id)).credits
    monkeypatch.setattr("app.payments.routes.settings.MP_WEBHOOK_SECRET", "secret")

    class _Sdk:
        class payment:
            @staticmethod
            def get(_payment_id):
                return {"response": _authoritative_payment(purchase, "approved")}

    monkeypatch.setattr("app.payments.service._get_sdk", lambda: _Sdk())

    # 1) Primeiro webhook: credita
    first = await client.post(
        "/api/v1/webhooks/mercadopago",
        json={"action": "payment.updated", "data": {"id": "123"}},
        headers=_signed_headers(),
    )
    assert first.json()["status"] == "credited", "First approved webhook must credit."

    # 2) Replay do mesmo payment_id: nao re-credita
    second = await client.post(
        "/api/v1/webhooks/mercadopago",
        json={"action": "payment.updated", "data": {"id": "123"}},
        headers=_signed_headers(),
    )
    assert second.json()["status"] == "not_credited", "Duplicate MP webhook must not re-credit."

    refreshed_user = await db_session.get(User, verified_user.id)
    assert (
        refreshed_user.credits == credits_before + 30
    ), "Replay must leave the balance exactly at one-credit increment."
