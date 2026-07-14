from __future__ import annotations

import json

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.config import Settings
from app.db.models import CreditAdjustment, CreditPurchase, PaymentCheckoutDispatch, User


def test_public_welcome_bonus_configuration_rejects_legacy_twenty_credit_value():
    with pytest.raises(ValidationError):
        Settings(WELCOME_CREDIT_BONUS=20)
    with pytest.raises(ValidationError):
        Settings(PURCHASE_BONUS_PERCENT=0)


def test_fixed_credit_offer_configuration_accepts_environment_strings():
    configured = Settings(
        _env_file=None,
        WELCOME_CREDIT_BONUS="2",
        PURCHASE_BONUS_PERCENT="20",
    )

    assert configured.WELCOME_CREDIT_BONUS == 2
    assert configured.PURCHASE_BONUS_PERCENT == 20
    with pytest.raises(ValidationError):
        Settings(_env_file=None, WELCOME_CREDIT_BONUS="20")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, PURCHASE_BONUS_PERCENT="0")


@pytest.mark.asyncio
@pytest.mark.parametrize("selected_package", [None, "starter", "popular", "professional"])
async def test_registration_starts_at_zero_and_persists_public_package_intent(
    client,
    db_session,
    selected_package,
):
    email = f"register-{selected_package or 'none'}@example.com"
    payload = {
        "email": email,
        "name": "Novo Usuario",
        "password": "StrongPass1",
        "consent": True,
    }
    if selected_package is not None:
        payload["selected_package"] = selected_package

    response = await client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 201
    db_session.expire_all()
    user = await db_session.scalar(select(User).where(User.email == email))
    assert user is not None
    assert user.credits == 0
    assert user.email_verified is False
    assert user.selected_package == selected_package


@pytest.mark.asyncio
async def test_registration_rejects_unknown_public_package_intent(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "unknown-package@example.com",
            "name": "Novo Usuario",
            "password": "StrongPass1",
            "consent": True,
            "selected_package": "enterprise",
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_me_and_export_expose_selected_package(client, db_session, verified_user, auth_headers):
    verified_user.selected_package = "professional"
    await db_session.merge(verified_user)
    await db_session.commit()

    me = await client.get("/api/v1/auth/me", headers=auth_headers(verified_user))
    exported = await client.get("/api/v1/auth/export-data", headers=auth_headers(verified_user))

    assert me.status_code == 200
    assert me.json()["selected_package"] == "professional"
    assert exported.status_code == 200
    assert exported.json()["user"]["selected_package"] == "professional"


@pytest.mark.asyncio
async def test_verification_adds_two_to_existing_balance_once_without_starting_checkout(
    client,
    db_session,
    user_factory,
):
    user = await user_factory(
        email="verify-package@example.com",
        credits=7,
        verified=False,
        verification_code="123456",
    )
    user.selected_package = "popular"
    await db_session.merge(user)
    await db_session.commit()

    first = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": user.email, "code": "123456"},
    )
    second = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": user.email, "code": "123456"},
    )

    assert first.status_code == second.status_code == 200
    assert first.json() == {"status": "verified", "credits": 2}
    assert second.json() == {"status": "already_verified"}
    db_session.expire_all()
    persisted = await db_session.get(User, user.id)
    assert persisted is not None
    assert persisted.credits == 9
    assert persisted.selected_package == "popular"
    assert await db_session.scalar(select(func.count(CreditPurchase.id))) == 0
    assert await db_session.scalar(select(func.count(PaymentCheckoutDispatch.id))) == 0


@pytest.mark.asyncio
async def test_public_packages_are_authoritative_and_need_no_token(client, monkeypatch):
    monkeypatch.setattr("app.payments.routes.settings.PURCHASE_BONUS_PERCENT", 20)

    response = await client.get("/api/v1/credits/packages")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": "starter",
            "selected_package": "starter",
            "name": "Starter",
            "credits": 10,
            "base_credits": 10,
            "price_brl": 1990,
            "price_display": "R$ 19,90",
            "bonus_percent": 20,
            "bonus_credits": 2,
            "total_credits": 12,
            "equivalences": {
                "standard_voice": 12,
                "premium_voice": 6,
                "dialogue": 6,
                "script_refinement": 24,
                "ai_image": 2,
                "ai_video": 0,
            },
        },
        {
            "id": "popular",
            "selected_package": "popular",
            "name": "Popular",
            "credits": 30,
            "base_credits": 30,
            "price_brl": 4990,
            "price_display": "R$ 49,90",
            "bonus_percent": 20,
            "bonus_credits": 6,
            "total_credits": 36,
            "equivalences": {
                "standard_voice": 36,
                "premium_voice": 18,
                "dialogue": 18,
                "script_refinement": 72,
                "ai_image": 7,
                "ai_video": 1,
            },
        },
        {
            "id": "professional",
            "selected_package": "professional",
            "name": "Profissional",
            "credits": 100,
            "base_credits": 100,
            "price_brl": 12990,
            "price_display": "R$ 129,90",
            "bonus_percent": 20,
            "bonus_credits": 20,
            "total_credits": 120,
            "equivalences": {
                "standard_voice": 120,
                "premium_voice": 60,
                "dialogue": 60,
                "script_refinement": 240,
                "ai_image": 24,
                "ai_video": 4,
            },
        },
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("requested_package", ["professional", "pro"])
async def test_checkout_accepts_professional_and_legacy_pro_but_freezes_internal_canonical_package(
    db_session,
    verified_user,
    monkeypatch,
    requested_package,
):
    from app.payments.checkout_outbox import create_or_resume_checkout

    monkeypatch.setattr("app.payments.checkout_outbox.settings.PURCHASE_BONUS_PERCENT", 20)

    outcome = await create_or_resume_checkout(
        verified_user,
        requested_package,
        "stripe",
        db_session,
        request_key=f"release-b-{requested_package}",
        attempt_inline=False,
    )

    purchase = await db_session.get(CreditPurchase, outcome.purchase_id)
    dispatch = await db_session.get(PaymentCheckoutDispatch, outcome.dispatch_id)
    assert purchase is not None and dispatch is not None
    assert purchase.package_name == "pro"
    assert purchase.credits_amount == 100
    assert purchase.bonus_credits == 20
    frozen = json.loads(dispatch.request_payload)
    assert frozen["metadata"]["package"] == "pro"
    assert frozen["metadata"]["credits"] == "100"
    assert frozen["metadata"]["bonus"] == "20"


@pytest.mark.asyncio
async def test_admin_adjustment_rejects_negative_result_atomically(
    client,
    db_session,
    admin_user,
    verified_user,
    auth_headers,
):
    response = await client.post(
        f"/api/v1/admin/users/{verified_user.id}/adjust-credits",
        json={"delta": -100, "reason": "estorno manual"},
        headers=auth_headers(admin_user),
    )

    assert response.status_code == 409
    db_session.expire_all()
    assert (await db_session.get(User, verified_user.id)).credits == 5
    adjustments = await db_session.scalar(select(func.count(CreditAdjustment.id)))
    assert adjustments == 0
