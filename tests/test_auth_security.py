from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt
from sqlalchemy import select

from app.config import settings
from app.db.models import User


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_409(client):
    payload = {"email": "dup@example.com", "name": "Dup", "password": "Secret123"}
    first = await client.post("/api/v1/auth/register", json=payload)
    second = await client.post("/api/v1/auth/register", json=payload)

    assert first.status_code == 201, "First registration should succeed."
    assert second.status_code == 409, "Duplicate registration must return 409."


@pytest.mark.asyncio
async def test_register_normalizes_email_and_hashes_password(client, db_session):
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "  TEST@Example.COM ", "name": "User", "password": "Secret123"},
    )

    assert response.status_code == 201, "Registration with normalized email should succeed."

    user = await db_session.scalar(select(User).where(User.email == "test@example.com"))
    assert user is not None, "Registered user should be stored with a normalized email."
    assert user.password_hash != "secret1", "Password must be stored as a hash."


@pytest.mark.asyncio
async def test_register_records_lgpd_consent_audit_trail(client, db_session):
    """LGPD: quando o cadastro declara consent=True, o backend registra
    comprovante de aceite (consented_at + IP) para auditoria."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "consent@example.com", "name": "Consent", "password": "Secret123", "consent": True},
    )
    assert response.status_code == 201
    user = await db_session.scalar(select(User).where(User.email == "consent@example.com"))
    assert user is not None
    assert user.consented_at is not None, "Deve registrar timestamp do consentimento."
    assert user.consent_ip, "Deve registrar IP do consentimento."


@pytest.mark.asyncio
async def test_login_wrong_password_and_missing_user_share_401(client):
    register = {"email": "login@example.com", "name": "Login", "password": "Secret123"}
    await client.post("/api/v1/auth/register", json=register)

    wrong_password = await client.post(
        "/api/v1/auth/login",
        json={"email": register["email"], "password": "badpass"},
    )
    missing_user = await client.post(
        "/api/v1/auth/login",
        json={"email": "missing@example.com", "password": "badpass"},
    )

    assert wrong_password.status_code == 401, "Wrong-password login must return 401."
    assert missing_user.status_code == 401, "Missing-user login must also return 401."
    assert (
        wrong_password.json()["detail"] == missing_user.json()["detail"]
    ), "Auth failures should not leak which credential was wrong."


@pytest.mark.asyncio
async def test_invalid_and_expired_tokens_return_401(client, verified_user, auth_headers):
    wrong_secret = jwt.encode(
        {"sub": str(verified_user.id), "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        "wrong-secret",
        algorithm=settings.JWT_ALGORITHM,
    )
    expired = jwt.encode(
        {"sub": str(verified_user.id), "exp": datetime.now(timezone.utc) - timedelta(minutes=5)},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    malformed = jwt.encode(
        {"exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )

    ok = await client.get("/api/v1/auth/me", headers=auth_headers(verified_user))
    bad_secret = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {wrong_secret}"})
    expired_resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired}"})
    malformed_resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {malformed}"})

    assert ok.status_code == 200, "Valid tokens should allow /me."
    assert bad_secret.status_code == 401, "Wrong-secret tokens must be rejected."
    assert expired_resp.status_code == 401, "Expired tokens must be rejected."
    assert malformed_resp.status_code == 401, "Tokens without sub must be rejected."


@pytest.mark.asyncio
async def test_protected_endpoints_require_auth_and_webhook_stays_public(client):
    protected = [
        ("GET", "/api/v1/auth/me", None),
        ("POST", "/api/v1/generate", {"topic": "Tema valido", "style": "educational", "duration_target": 45}),
        ("GET", "/api/v1/jobs", None),
        ("POST", "/api/v1/credits/checkout", {"package": "starter"}),
        ("GET", "/api/v1/credits/history", None),
    ]

    for method, path, payload in protected:
        response = await client.request(method, path, json=payload)
        assert response.status_code in {401, 403}, f"{path} should reject anonymous access."

    webhook = await client.post("/api/v1/webhooks/mercadopago", content=b"{}")
    assert webhook.status_code == 200, "MercadoPago webhook should remain publicly accessible."


@pytest.mark.asyncio
async def test_cors_preflight_allows_known_origin_and_blocks_unknown(client):
    allowed = await client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://localhost:3003",
            "Access-Control-Request-Method": "POST",
        },
    )
    blocked = await client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert (
        allowed.headers.get("access-control-allow-origin") == "http://localhost:3003"
    ), "Configured frontend origin should be allowed by CORS."
    assert (
        blocked.headers.get("access-control-allow-origin") is None
    ), "Unknown origins should not receive an allow-origin header."
