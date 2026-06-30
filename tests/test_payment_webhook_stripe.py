"""Stripe como segundo provedor: checkout, crédito idempotente, Pix pendente, assinatura, estorno.

Espelha os testes do Mercado Pago. O caminho SEM webhook secret re-verifica via API (retrieve);
mockamos stripe.checkout.Session.retrieve / stripe.Charge.retrieve para simular a resposta confiável.
"""

from types import SimpleNamespace

import pytest
import stripe

from app.db.models import CreditPurchase, User


@pytest.mark.asyncio
async def test_stripe_checkout_creates_pending_purchase(client, db_session, verified_user, auth_headers, monkeypatch):
    monkeypatch.setattr("app.payments.service.settings.STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setattr(
        stripe.checkout.Session,
        "create",
        staticmethod(lambda **kw: SimpleNamespace(id="cs_test_1", url="https://stripe.test/checkout")),
    )

    response = await client.post(
        "/api/v1/credits/checkout",
        headers=auth_headers(verified_user),
        json={"package": "starter", "provider": "stripe"},
    )

    assert response.status_code == 200, "Stripe checkout should succeed for valid packages."
    purchase = await db_session.get(CreditPurchase, response.json()["purchase_id"])
    assert purchase is not None
    assert purchase.provider == "stripe", "Stripe purchase must record the provider."
    assert purchase.status == "pending"
    assert purchase.mp_preference_id == "cs_test_1", "Stripe session id is stored in the checkout id column."


@pytest.mark.asyncio
async def test_checkout_rejects_invalid_provider(client, verified_user, auth_headers):
    response = await client.post(
        "/api/v1/credits/checkout",
        headers=auth_headers(verified_user),
        json={"package": "starter", "provider": "paypal"},
    )
    assert response.status_code == 400, "Unknown payment providers must be rejected."


def _patch_retrieve(monkeypatch, session_obj):
    monkeypatch.setattr("app.payments.routes.settings.STRIPE_WEBHOOK_SECRET", "")
    monkeypatch.setattr(stripe.checkout.Session, "retrieve", staticmethod(lambda _id: session_obj))


@pytest.mark.asyncio
async def test_stripe_webhook_credits_on_paid_via_api(client, db_session, purchase_factory, verified_user, monkeypatch):
    purchase = await purchase_factory(package_name="popular", provider="stripe")
    _patch_retrieve(
        monkeypatch,
        {
            "id": "cs_test_1",
            "payment_status": "paid",
            "client_reference_id": str(purchase.id),
            "payment_intent": "pi_test_1",
        },
    )

    response = await client.post(
        "/api/v1/webhooks/stripe",
        json={"type": "checkout.session.completed", "data": {"object": {"id": "cs_test_1"}}},
    )

    assert response.json()["status"] == "credited", "Paid Stripe checkout should credit the purchase."
    refreshed_purchase = await db_session.get(CreditPurchase, purchase.id)
    refreshed_user = await db_session.get(User, verified_user.id)
    assert refreshed_purchase.status == "approved"
    assert refreshed_purchase.mp_payment_id == "pi_test_1", "Stripe payment_intent stored for refunds."
    assert refreshed_user.credits == 35, "Popular package credits 30 once (initial 5)."


@pytest.mark.asyncio
async def test_stripe_webhook_is_idempotent(client, db_session, purchase_factory, verified_user, monkeypatch):
    purchase = await purchase_factory(package_name="popular", provider="stripe")
    _patch_retrieve(
        monkeypatch,
        {
            "id": "cs_test_1",
            "payment_status": "paid",
            "client_reference_id": str(purchase.id),
            "payment_intent": "pi_test_1",
        },
    )
    body = {"type": "checkout.session.completed", "data": {"object": {"id": "cs_test_1"}}}

    first = await client.post("/api/v1/webhooks/stripe", json=body)
    second = await client.post("/api/v1/webhooks/stripe", json=body)

    assert first.json()["status"] == "credited"
    assert second.json()["status"] == "not_credited", "Duplicate Stripe webhook must not re-credit."
    refreshed_user = await db_session.get(User, verified_user.id)
    assert refreshed_user.credits == 35, "Idempotent: credited exactly once."


@pytest.mark.asyncio
async def test_stripe_pix_pending_does_not_credit(client, db_session, purchase_factory, verified_user, monkeypatch):
    purchase = await purchase_factory(package_name="popular", provider="stripe")
    credits_before = (await db_session.get(User, verified_user.id)).credits
    _patch_retrieve(
        monkeypatch,
        {
            "id": "cs_test_1",
            "payment_status": "unpaid",  # Pix ainda nao confirmado
            "client_reference_id": str(purchase.id),
            "payment_intent": "pi_test_1",
        },
    )

    response = await client.post(
        "/api/v1/webhooks/stripe",
        json={"type": "checkout.session.completed", "data": {"object": {"id": "cs_test_1"}}},
    )

    assert response.json()["status"] == "not_credited", "Unpaid Pix session must not credit yet."
    assert (await db_session.get(User, verified_user.id)).credits == credits_before


@pytest.mark.asyncio
async def test_stripe_webhook_with_valid_signature_credits(
    client, db_session, purchase_factory, verified_user, monkeypatch
):
    purchase = await purchase_factory(package_name="starter", provider="stripe")
    monkeypatch.setattr("app.payments.routes.settings.STRIPE_WEBHOOK_SECRET", "whsec_test")
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_1",
                "payment_status": "paid",
                "client_reference_id": str(purchase.id),
                "payment_intent": "pi_test_1",
            }
        },
    }
    # Assinatura real e verificada pelo Stripe SDK; aqui mockamos construct_event (já confiável).
    monkeypatch.setattr(stripe.Webhook, "construct_event", staticmethod(lambda payload, sig, secret: event))

    response = await client.post(
        "/api/v1/webhooks/stripe",
        json=event,
        headers={"stripe-signature": "t=1,v1=whatever"},
    )

    assert response.json()["status"] == "credited"
    assert (await db_session.get(CreditPurchase, purchase.id)).status == "approved"


@pytest.mark.asyncio
async def test_stripe_webhook_invalid_signature_rejected(client, monkeypatch):
    monkeypatch.setattr("app.payments.routes.settings.STRIPE_WEBHOOK_SECRET", "whsec_test")

    def _boom(payload, sig, secret):
        raise ValueError("bad signature")

    monkeypatch.setattr(stripe.Webhook, "construct_event", staticmethod(_boom))

    response = await client.post(
        "/api/v1/webhooks/stripe",
        json={"type": "checkout.session.completed", "data": {"object": {"id": "cs_test_1"}}},
        headers={"stripe-signature": "t=1,v1=bad"},
    )
    assert response.json()["status"] == "invalid_signature", "Bad Stripe signature must be rejected."


@pytest.mark.asyncio
async def test_stripe_refund_reverts_credits(client, db_session, purchase_factory, verified_user, monkeypatch):
    purchase = await purchase_factory(
        package_name="popular", provider="stripe", status="approved", mp_payment_id="pi_test_1"
    )
    user = await db_session.get(User, verified_user.id)
    user.credits += purchase.credits_amount  # simula que ja foi creditado
    await db_session.commit()
    credits_with_purchase = user.credits

    monkeypatch.setattr("app.payments.routes.settings.STRIPE_WEBHOOK_SECRET", "")
    monkeypatch.setattr(
        stripe.Charge, "retrieve", staticmethod(lambda _id: {"id": "ch_1", "payment_intent": "pi_test_1"})
    )

    response = await client.post(
        "/api/v1/webhooks/stripe",
        json={"type": "charge.refunded", "data": {"object": {"id": "ch_1"}}},
    )

    assert response.status_code == 200
    db_session.expire_all()  # webhook commitou noutra sessao; recarrega do DB (sem identity-map stale)
    refreshed_purchase = await db_session.get(CreditPurchase, purchase.id)
    refreshed_user = await db_session.get(User, verified_user.id)
    assert refreshed_purchase.status == "refunded"
    assert refreshed_user.credits == credits_with_purchase - purchase.credits_amount
