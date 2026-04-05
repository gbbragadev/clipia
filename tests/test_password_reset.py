from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt
from sqlalchemy import select

from app.auth import routes as auth_routes
from app.auth.service import create_access_token, hash_password, verify_password
from app.config import settings
from app.db.models import User


def _ensure_utc(dt):
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_forgot_password_updates_code_and_sends_email(client, db_session, user_factory):
    user = await user_factory(
        email="reset@example.com",
        name="Reset User",
        password_hash=hash_password("oldsecret"),
        verified=False,
        verification_code="111111",
        verification_expires=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    auth_routes.send_password_reset_email.reset_mock()

    response = await client.post("/api/v1/auth/forgot-password", json={"email": user.email})

    assert response.status_code == 200, "Forgot-password should always return success."
    assert response.json()["status"] == "code_sent", "Forgot-password should return code_sent."
    assert auth_routes.send_password_reset_email.call_count == 1, "Existing users should receive a reset email."

    refreshed = await db_session.get(User, user.id)
    assert refreshed.verification_code != "111111", "Forgot-password should replace the previous code."
    assert refreshed.verification_code and len(refreshed.verification_code) == 6, "Forgot-password should generate a six-digit code."
    assert refreshed.verification_expires and _ensure_utc(refreshed.verification_expires) > datetime.now(timezone.utc), "Reset code should have a future expiry."


@pytest.mark.asyncio
async def test_forgot_password_with_missing_email_is_not_leaky(client):
    auth_routes.send_password_reset_email.reset_mock()

    response = await client.post("/api/v1/auth/forgot-password", json={"email": "missing@example.com"})

    assert response.status_code == 200, "Forgot-password should not reveal whether the email exists."
    assert response.json()["status"] == "code_sent", "Forgot-password should still return code_sent for missing emails."
    assert auth_routes.send_password_reset_email.call_count == 0, "Missing users should not trigger email delivery."


@pytest.mark.asyncio
async def test_verify_reset_code_returns_reset_token(client, user_factory):
    user = await user_factory(
        email="verify-reset@example.com",
        password_hash=hash_password("oldsecret"),
        verified=False,
        verification_code="222222",
        verification_expires=datetime.now(timezone.utc) + timedelta(minutes=10),
    )

    response = await client.post(
        "/api/v1/auth/verify-reset-code",
        json={"email": user.email, "code": "222222"},
    )

    assert response.status_code == 200, "Correct reset code should verify."
    body = response.json()
    assert body["status"] == "verified", "Reset verification should report verified."
    decoded = jwt.decode(body["reset_token"], settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    assert decoded["sub"] == str(user.id), "Reset token should belong to the matching user."
    assert decoded["purpose"] == "reset", "Reset token must be marked with purpose=reset."


@pytest.mark.asyncio
async def test_verify_reset_code_rejects_wrong_and_expired_codes(client, user_factory):
    wrong_user = await user_factory(
        email="wrong-reset@example.com",
        password_hash=hash_password("oldsecret"),
        verified=False,
        verification_code="333333",
        verification_expires=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    expired_user = await user_factory(
        email="expired-reset@example.com",
        password_hash=hash_password("oldsecret"),
        verified=False,
        verification_code="444444",
        verification_expires=datetime.now(timezone.utc) - timedelta(minutes=1),
    )

    wrong = await client.post(
        "/api/v1/auth/verify-reset-code",
        json={"email": wrong_user.email, "code": "999999"},
    )
    expired = await client.post(
        "/api/v1/auth/verify-reset-code",
        json={"email": expired_user.email, "code": "444444"},
    )

    assert wrong.status_code == 400, "Wrong reset codes should be rejected."
    assert expired.status_code == 400, "Expired reset codes should be rejected."


@pytest.mark.asyncio
async def test_reset_password_with_valid_token_changes_password_and_clears_otp(client, db_session, user_factory):
    user = await user_factory(
        email="change@example.com",
        password_hash=hash_password("oldsecret"),
        verified=False,
        verification_code="555555",
        verification_expires=datetime.now(timezone.utc) + timedelta(minutes=10),
    )

    verify = await client.post(
        "/api/v1/auth/verify-reset-code",
        json={"email": user.email, "code": "555555"},
    )
    reset_token = verify.json()["reset_token"]

    response = await client.post(
        "/api/v1/auth/reset-password",
        json={"reset_token": reset_token, "new_password": "newsecret"},
    )

    assert response.status_code == 200, "Reset-password should succeed with a valid reset token."
    assert response.json()["status"] == "password_reset", "Successful resets should report password_reset."

    refreshed = await db_session.get(User, user.id)
    assert verify_password("newsecret", refreshed.password_hash), "New password should be persisted as a hash."
    assert not verify_password("oldsecret", refreshed.password_hash), "Old password should no longer work."
    assert refreshed.verification_code is None, "Reset password should clear the OTP."
    assert refreshed.verification_expires is None, "Reset password should clear the OTP expiry."

    login_new = await client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "newsecret"},
    )
    login_old = await client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "oldsecret"},
    )

    assert login_new.status_code == 200, "Login should work with the new password."
    assert login_old.status_code == 401, "Login should fail with the old password."


@pytest.mark.asyncio
async def test_reset_password_rejects_expired_and_wrong_purpose_tokens(client, user_factory):
    user = await user_factory(
        email="token@example.com",
        password_hash=hash_password("oldsecret"),
        verified=False,
        verification_code="666666",
        verification_expires=datetime.now(timezone.utc) + timedelta(minutes=10),
    )

    expired_token = jwt.encode(
        {
            "sub": str(user.id),
            "purpose": "reset",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    wrong_purpose_token = create_access_token(str(user.id))

    expired = await client.post(
        "/api/v1/auth/reset-password",
        json={"reset_token": expired_token, "new_password": "newsecret"},
    )
    wrong_purpose = await client.post(
        "/api/v1/auth/reset-password",
        json={"reset_token": wrong_purpose_token, "new_password": "newsecret"},
    )

    assert expired.status_code == 400, "Expired reset tokens should be rejected."
    assert wrong_purpose.status_code == 400, "Tokens without purpose=reset should be rejected."
