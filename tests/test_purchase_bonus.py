"""Promo beta: PURCHASE_BONUS_PERCENT credita bonus junto com a compra.

O bonus e aplicado em _credit_once (ponto unico MP+Stripe) e persistido em
CreditPurchase.bonus_credits (snapshot), para que o estorno reverta base+bonus
mesmo depois que a promocao acabar.
"""

import pytest
import stripe

from app.db.models import CreditPurchase, User


def _patch_retrieve(monkeypatch, session_obj):
    monkeypatch.setattr("app.payments.routes.settings.STRIPE_WEBHOOK_SECRET", "")
    monkeypatch.setattr(stripe.checkout.Session, "retrieve", staticmethod(lambda _id: session_obj))


def _paid_session(purchase, payment_intent="pi_bonus_1"):
    return {
        "id": "cs_bonus_1",
        "payment_status": "paid",
        "client_reference_id": str(purchase.id),
        "payment_intent": payment_intent,
    }


_WEBHOOK_BODY = {"type": "checkout.session.completed", "data": {"object": {"id": "cs_bonus_1"}}}


@pytest.mark.asyncio
async def test_purchase_bonus_credited_with_flag_on(client, db_session, purchase_factory, verified_user, monkeypatch):
    monkeypatch.setattr("app.payments.service.settings.PURCHASE_BONUS_PERCENT", 20)
    purchase = await purchase_factory(package_name="popular", provider="stripe")
    _patch_retrieve(monkeypatch, _paid_session(purchase))

    response = await client.post("/api/v1/webhooks/stripe", json=_WEBHOOK_BODY)

    assert response.json()["status"] == "credited"
    db_session.expire_all()
    refreshed_purchase = await db_session.get(CreditPurchase, purchase.id)
    refreshed_user = await db_session.get(User, verified_user.id)
    assert refreshed_purchase.bonus_credits == 6, "20% de 30 creditos = 6 de bonus (snapshot na compra)."
    assert refreshed_user.credits == 5 + 30 + 6, "Base + bonus creditados juntos (inicial 5)."


@pytest.mark.asyncio
async def test_purchase_bonus_replay_is_idempotent(client, db_session, purchase_factory, verified_user, monkeypatch):
    monkeypatch.setattr("app.payments.service.settings.PURCHASE_BONUS_PERCENT", 20)
    purchase = await purchase_factory(package_name="popular", provider="stripe")
    _patch_retrieve(monkeypatch, _paid_session(purchase))

    first = await client.post("/api/v1/webhooks/stripe", json=_WEBHOOK_BODY)
    second = await client.post("/api/v1/webhooks/stripe", json=_WEBHOOK_BODY)

    assert first.json()["status"] == "credited"
    assert second.json()["status"] == "not_credited", "Replay nao pode re-creditar base nem bonus."
    db_session.expire_all()
    assert (await db_session.get(User, verified_user.id)).credits == 41


@pytest.mark.asyncio
async def test_refund_reverts_base_and_bonus_even_after_promo_ends(
    client, db_session, purchase_factory, verified_user, monkeypatch
):
    monkeypatch.setattr("app.payments.service.settings.PURCHASE_BONUS_PERCENT", 20)
    purchase = await purchase_factory(package_name="popular", provider="stripe")
    _patch_retrieve(monkeypatch, _paid_session(purchase))
    await client.post("/api/v1/webhooks/stripe", json=_WEBHOOK_BODY)  # credita 30+6

    # Promo acabou entre a compra e o estorno — o snapshot em bonus_credits garante a reversao total.
    monkeypatch.setattr("app.payments.service.settings.PURCHASE_BONUS_PERCENT", 0)
    monkeypatch.setattr(
        stripe.Charge, "retrieve", staticmethod(lambda _id: {"id": "ch_1", "payment_intent": "pi_bonus_1"})
    )

    response = await client.post(
        "/api/v1/webhooks/stripe",
        json={"type": "charge.refunded", "data": {"object": {"id": "ch_1"}}},
    )

    assert response.status_code == 200
    db_session.expire_all()
    assert (await db_session.get(CreditPurchase, purchase.id)).status == "refunded"
    assert (await db_session.get(User, verified_user.id)).credits == 5, "Estorno devolve base E bonus."


@pytest.mark.asyncio
async def test_bonus_zero_when_flag_off(client, db_session, purchase_factory, verified_user, monkeypatch):
    purchase = await purchase_factory(package_name="popular", provider="stripe")
    _patch_retrieve(monkeypatch, _paid_session(purchase))

    response = await client.post("/api/v1/webhooks/stripe", json=_WEBHOOK_BODY)

    assert response.json()["status"] == "credited"
    db_session.expire_all()
    assert (await db_session.get(CreditPurchase, purchase.id)).bonus_credits == 0
    assert (await db_session.get(User, verified_user.id)).credits == 35, "Sem promo: comportamento atual."


@pytest.mark.asyncio
async def test_packages_endpoint_exposes_bonus(client, verified_user, auth_headers, monkeypatch):
    monkeypatch.setattr("app.payments.routes.settings.PURCHASE_BONUS_PERCENT", 20)

    response = await client.get("/api/v1/credits/packages", headers=auth_headers(verified_user))

    assert response.status_code == 200
    pkgs = {p["id"]: p for p in response.json()}
    assert pkgs["starter"]["bonus_credits"] == 2
    assert pkgs["popular"]["bonus_credits"] == 6
    assert pkgs["pro"]["bonus_credits"] == 20
    assert pkgs["popular"]["bonus_percent"] == 20


@pytest.mark.asyncio
async def test_packages_endpoint_bonus_zero_by_default(client, verified_user, auth_headers):
    response = await client.get("/api/v1/credits/packages", headers=auth_headers(verified_user))

    assert response.status_code == 200
    for pkg in response.json():
        assert pkg["bonus_percent"] == 0
        assert pkg["bonus_credits"] == 0
