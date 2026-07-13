"""Stripe como segundo provedor: checkout, crédito idempotente, Pix pendente, assinatura, estorno.

Espelha os testes do Mercado Pago. O caminho SEM webhook secret re-verifica via API (retrieve);
mockamos stripe.checkout.Session.retrieve / stripe.Charge.retrieve para simular a resposta confiável.
"""

import time
from types import SimpleNamespace

import pytest
import stripe
from sqlalchemy import func, select

from app.db.models import CreditPurchase, ProcessedPaymentEvent, User


@pytest.mark.asyncio
async def test_stripe_checkout_creates_pending_purchase(client, db_session, verified_user, auth_headers, monkeypatch):
    session_id = "cs_test_a12345678"
    monkeypatch.setattr("app.payments.service.settings.STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setattr(
        stripe.checkout.Session,
        "create",
        staticmethod(
            lambda **kw: SimpleNamespace(
                id=session_id,
                url=f"https://checkout.stripe.com/c/pay/{session_id}",
            )
        ),
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
    assert purchase.mp_preference_id == session_id, "Stripe session id is stored in the checkout id column."


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


def _authoritative_session(
    purchase,
    *,
    payment_status="paid",
    payment_intent="pi_test_1",
    status="complete",
):
    return {
        "id": purchase.mp_preference_id,
        "status": status,
        "payment_status": payment_status,
        "client_reference_id": str(purchase.id),
        "metadata": {"purchase_id": str(purchase.id)},
        "amount_total": purchase.price_brl,
        "currency": "brl",
        "payment_intent": payment_intent,
    }


def _patch_full_refund(monkeypatch, purchase, payment_intent="pi_test_1"):
    monkeypatch.setattr(
        stripe.Charge,
        "retrieve",
        staticmethod(
            lambda _id: {
                "id": "ch_1",
                "payment_intent": payment_intent,
                "amount": purchase.price_brl,
                "amount_refunded": purchase.price_brl,
                "currency": "brl",
                "refunded": True,
            }
        ),
    )
    monkeypatch.setattr(
        stripe.PaymentIntent,
        "retrieve",
        staticmethod(lambda _id: {"id": payment_intent, "metadata": {"purchase_id": str(purchase.id)}}),
    )


@pytest.mark.asyncio
async def test_stripe_webhook_credits_on_paid_via_api(client, db_session, purchase_factory, verified_user, monkeypatch):
    purchase = await purchase_factory(package_name="popular", provider="stripe")
    _patch_retrieve(
        monkeypatch,
        _authoritative_session(purchase),
    )

    response = await client.post(
        "/api/v1/webhooks/stripe",
        json={"type": "checkout.session.completed", "data": {"object": {"id": "cs_test_1"}}},
    )

    assert response.json()["status"] == "processed", "Paid Stripe checkout should credit the purchase."
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
        _authoritative_session(purchase),
    )
    body = {"type": "checkout.session.completed", "data": {"object": {"id": "cs_test_1"}}}

    first = await client.post("/api/v1/webhooks/stripe", json=body)
    second = await client.post("/api/v1/webhooks/stripe", json=body)

    assert first.json()["status"] == "processed"
    assert second.json()["status"] == "not_processed", "Duplicate Stripe webhook must not re-credit."
    refreshed_user = await db_session.get(User, verified_user.id)
    assert refreshed_user.credits == 35, "Idempotent: credited exactly once."


@pytest.mark.asyncio
async def test_stripe_pix_pending_does_not_credit(client, db_session, purchase_factory, verified_user, monkeypatch):
    purchase = await purchase_factory(package_name="popular", provider="stripe")
    credits_before = (await db_session.get(User, verified_user.id)).credits
    _patch_retrieve(
        monkeypatch,
        _authoritative_session(purchase, payment_status="unpaid"),
    )

    response = await client.post(
        "/api/v1/webhooks/stripe",
        json={"type": "checkout.session.completed", "data": {"object": {"id": "cs_test_1"}}},
    )

    assert response.json()["status"] == "not_processed", "Unpaid Pix session must not credit yet."
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
                "metadata": {"purchase_id": str(purchase.id)},
                "amount_total": purchase.price_brl,
                "currency": "brl",
                "payment_intent": "pi_test_1",
            }
        },
    }
    # Assinatura real e verificada pelo Stripe SDK; aqui mockamos construct_event (já confiável).
    monkeypatch.setattr(stripe.Webhook, "construct_event", staticmethod(lambda payload, sig, secret: event))

    response = await client.post(
        "/api/v1/webhooks/stripe",
        json=event,
        headers={"stripe-signature": f"t={int(time.time())},v1=whatever"},
    )

    assert response.json()["status"] == "processed"
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
        headers={"stripe-signature": f"t={int(time.time())},v1=bad"},
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
    _patch_full_refund(monkeypatch, purchase)

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


@pytest.mark.asyncio
async def test_unsigned_stripe_refund_rejects_charge_object_with_different_retrieved_id(
    client, db_session, purchase_factory, verified_user, monkeypatch
):
    purchase = await purchase_factory(
        package_name="popular", provider="stripe", status="approved", mp_payment_id="pi_test_1"
    )
    user = await db_session.get(User, verified_user.id)
    user.credits += purchase.credits_amount
    await db_session.commit()
    before = user.credits
    monkeypatch.setattr("app.payments.routes.settings.STRIPE_WEBHOOK_SECRET", "")
    monkeypatch.setattr(
        stripe.Charge,
        "retrieve",
        staticmethod(lambda _id: {"id": "ch_different"}),
    )

    response = await client.post(
        "/api/v1/webhooks/stripe",
        json={"type": "charge.refunded", "data": {"object": {"id": "ch_requested"}}},
    )

    assert response.json() == {"status": "unverified"}
    db_session.expire_all()
    assert (await db_session.get(CreditPurchase, purchase.id)).status == "approved"
    assert (await db_session.get(User, verified_user.id)).credits == before
    assert await db_session.scalar(select(func.count()).select_from(ProcessedPaymentEvent)) == 0


class _FakeStripeObj:
    """Simula o StripeObject do SDK>=15: NÃO é dict, dict(obj) quebra, mas tem .to_dict()."""

    def __init__(self, data: dict):
        self._data = data

    def to_dict(self) -> dict:
        return dict(self._data)

    def __iter__(self):
        raise KeyError(0)  # espelha o dict(session) -> KeyError 0 do SDK real


@pytest.mark.asyncio
async def test_stripe_webhook_credits_when_sdk_returns_object_not_dict(
    client, db_session, purchase_factory, verified_user, monkeypatch
):
    """Regressão: SDK stripe>=15 retorna objeto (não dict); dict(session) quebrava e nada creditava.
    Só o pagamento real pegou (dict nos mocks mascarava). Handler deve normalizar via to_dict."""
    purchase = await purchase_factory(package_name="starter", provider="stripe", mp_preference_id="cs_test_obj")
    obj = _FakeStripeObj(
        {
            "id": "cs_test_obj",
            "payment_status": "paid",
            "client_reference_id": str(purchase.id),
            "metadata": {"purchase_id": str(purchase.id)},
            "amount_total": purchase.price_brl,
            "currency": "brl",
            "payment_intent": "pi_test_obj",
        }
    )
    monkeypatch.setattr("app.payments.routes.settings.STRIPE_WEBHOOK_SECRET", "")
    monkeypatch.setattr(stripe.checkout.Session, "retrieve", staticmethod(lambda _id: obj))

    response = await client.post(
        "/api/v1/webhooks/stripe",
        json={"type": "checkout.session.completed", "data": {"object": {"id": "cs_test_obj"}}},
    )

    assert (
        response.json()["status"] == "processed"
    ), "SDK>=15 devolve objeto (não dict); handler deve normalizar via to_dict e creditar."
    assert (await db_session.get(CreditPurchase, purchase.id)).status == "approved"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("forged_type", "provider_status"),
    [
        ("checkout.session.expired", "open"),
        ("checkout.session.expired", "complete"),
        ("checkout.session.async_payment_failed", "open"),
        ("checkout.session.async_payment_failed", "complete"),
        ("checkout.session.async_payment_failed", "expired"),
    ],
)
async def test_unsigned_void_type_cannot_terminalize_without_matching_authoritative_provider_state(
    client,
    db_session,
    purchase_factory,
    verified_user,
    monkeypatch,
    forged_type,
    provider_status,
):
    purchase = await purchase_factory(provider="stripe")
    _patch_retrieve(
        monkeypatch,
        _authoritative_session(
            purchase,
            payment_status="unpaid",
            payment_intent=None,
            status=provider_status,
        ),
    )

    response = await client.post(
        "/api/v1/webhooks/stripe",
        json={"type": forged_type, "data": {"object": {"id": purchase.mp_preference_id}}},
    )

    assert response.json()["status"] == "unverified"
    db_session.expire_all()
    refreshed = await db_session.get(CreditPurchase, purchase.id)
    assert refreshed.status == "pending"
    assert refreshed.payment_state is None
    assert (await db_session.get(User, verified_user.id)).credits == 5
    assert await db_session.scalar(select(func.count()).select_from(ProcessedPaymentEvent)) == 0


@pytest.mark.asyncio
async def test_unsigned_expired_is_accepted_only_when_retrieved_session_is_authoritatively_expired(
    client,
    db_session,
    purchase_factory,
    monkeypatch,
):
    purchase = await purchase_factory(provider="stripe")
    _patch_retrieve(
        monkeypatch,
        _authoritative_session(
            purchase,
            payment_status="unpaid",
            payment_intent=None,
            status="expired",
        ),
    )

    response = await client.post(
        "/api/v1/webhooks/stripe",
        json={
            "type": "checkout.session.expired",
            "data": {"object": {"id": purchase.mp_preference_id}},
        },
    )

    assert response.json()["status"] == "processed"
    db_session.expire_all()
    refreshed = await db_session.get(CreditPurchase, purchase.id)
    assert refreshed.status == "pending"
    assert refreshed.payment_state == "void"
    assert refreshed.mp_payment_id is None
    assert await db_session.scalar(select(func.count()).select_from(ProcessedPaymentEvent)) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("event_type", ["checkout.session.expired", "checkout.session.async_payment_failed"])
async def test_signed_void_events_remain_authoritative(
    client,
    db_session,
    purchase_factory,
    monkeypatch,
    event_type,
):
    purchase = await purchase_factory(provider="stripe")
    monkeypatch.setattr("app.payments.routes.settings.STRIPE_WEBHOOK_SECRET", "whsec_test")
    event = {
        "id": f"evt_{event_type}",
        "type": event_type,
        "data": {
            "object": _authoritative_session(
                purchase,
                payment_status="unpaid",
                payment_intent=None,
                status="open",
            )
        },
    }
    monkeypatch.setattr(stripe.Webhook, "construct_event", staticmethod(lambda payload, sig, secret: event))

    response = await client.post(
        "/api/v1/webhooks/stripe",
        json={"attacker_controlled": "body is ignored after signature verification"},
        headers={"stripe-signature": f"t={int(time.time())},v1=signed"},
    )

    assert response.json()["status"] == "processed"
    db_session.expire_all()
    refreshed = await db_session.get(CreditPurchase, purchase.id)
    assert refreshed.status == "pending"
    assert refreshed.payment_state == "void"
    assert refreshed.mp_payment_id is None
    assert await db_session.scalar(select(func.count()).select_from(ProcessedPaymentEvent)) == 1
