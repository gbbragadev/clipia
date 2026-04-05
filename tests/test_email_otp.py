from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.db.models import User


@pytest.mark.asyncio
async def test_register_creates_pending_user_and_verify_grants_two_credits(client, db_session):
    register = await client.post(
        "/api/v1/auth/register",
        json={"email": "otp@example.com", "name": "Otp User", "password": "secret1"},
    )
    assert register.status_code == 201, "Registration should succeed for OTP flow."

    user = await db_session.scalar(select(User).where(User.email == "otp@example.com"))
    assert user is not None, "Registration should persist the new user."
    assert user.credits == 0, "Fresh registrations should start with zero credits."
    assert user.email_verified is False, "Fresh registrations should be unverified."
    assert user.verification_code.isdigit() and len(user.verification_code) == 6, "Registration should generate a six-digit OTP."

    verify = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": "otp@example.com", "code": user.verification_code},
    )
    assert verify.status_code == 200, "Correct OTP should verify the account."
    assert verify.json()["credits"] == 2, "Email verification should grant exactly two credits."

    await db_session.refresh(user)
    assert user.email_verified is True, "Verified users must be marked as verified."
    assert user.verification_code is None, "OTP should be cleared after successful verification."


@pytest.mark.asyncio
async def test_verify_email_rejects_wrong_and_expired_codes(client, user_factory):
    wrong_user = await user_factory(
        email="wrong@example.com",
        password_hash="hash",
        verification_code="123456",
        verification_expires=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    expired_user = await user_factory(
        email="expired@example.com",
        password_hash="hash",
        verification_code="123456",
        verification_expires=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    wrong_code = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": wrong_user.email, "code": "654321"},
    )
    expired = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": expired_user.email, "code": "123456"},
    )

    assert wrong_code.status_code == 400, "Wrong OTP should return 400."
    assert "incorreto" in wrong_code.json()["detail"].lower(), "Wrong OTP response should explain the failure."
    assert expired.status_code == 400, "Expired OTP should return 400."
    assert "expirado" in expired.json()["detail"].lower(), "Expired OTP response should explain the failure."


@pytest.mark.asyncio
async def test_verify_email_is_idempotent_for_verified_user(client, verified_user):
    response = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": verified_user.email, "code": "123456"},
    )

    assert response.status_code == 200, "Already-verified users should get an idempotent 200 response."
    assert response.json()["status"] == "already_verified", "Already-verified users should receive the already_verified status."


@pytest.mark.asyncio
async def test_resend_code_replaces_previous_code(client, db_session, unverified_user):
    old_code = unverified_user.verification_code

    response = await client.post(
        "/api/v1/auth/resend-code",
        json={"email": unverified_user.email},
    )
    assert response.status_code == 200, "Resend-code should succeed for unverified users."

    refreshed_user = await db_session.get(User, unverified_user.id)
    assert refreshed_user.verification_code != old_code, "Resend-code should replace the previous OTP."

    old_verify = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": unverified_user.email, "code": old_code},
    )
    assert old_verify.status_code == 400, "Old OTPs should become invalid after resend."


@pytest.mark.asyncio
async def test_unverified_user_cannot_generate_even_with_credits(client, db_session, unverified_user, auth_headers):
    db_user = await db_session.get(User, unverified_user.id)
    db_user.credits = 5
    await db_session.commit()

    response = await client.post(
        "/api/v1/generate",
        headers=auth_headers(unverified_user),
        json={"topic": "Tema valido para gerar", "style": "educational", "duration_target": 45},
    )

    assert response.status_code == 403, "Unverified users must be blocked from generation even when they have credits."
