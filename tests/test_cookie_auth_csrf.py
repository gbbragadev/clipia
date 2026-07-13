from datetime import datetime, timezone

import pytest
from fastapi import Response

from app.auth.service import create_reset_token
from app.auth.session import AUTH_COOKIE_NAME, CSRF_COOKIE_NAME, set_auth_cookies
from app.config import settings


async def _login(client, verified_user):
    return await client.post(
        "/api/v1/auth/login",
        json={"email": verified_user.email, "password": "supersecret"},
    )


@pytest.mark.asyncio
async def test_login_issues_host_only_http_only_session_and_bound_csrf(client, verified_user):
    response = await _login(client, verified_user)

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["csrf_token"]
    assert client.cookies.get(AUTH_COOKIE_NAME) == body["access_token"]
    assert client.cookies.get(CSRF_COOKIE_NAME) == body["csrf_token"]
    assert response.headers["cache-control"] == "no-store"

    cookies = response.headers.get_list("set-cookie")
    session_cookie = next(value for value in cookies if value.startswith(f"{AUTH_COOKIE_NAME}="))
    csrf_cookie = next(value for value in cookies if value.startswith(f"{CSRF_COOKIE_NAME}="))
    assert "HttpOnly" in session_cookie
    assert "SameSite=lax" in session_cookie
    assert "Domain=" not in session_cookie
    assert "HttpOnly" not in csrf_cookie
    assert "SameSite=lax" in csrf_cookie


def test_production_auth_cookies_are_secure(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    response = Response()

    set_auth_cookies(response, access_token="jwt", csrf_token="csrf")

    cookies = response.headers.getlist("set-cookie")
    assert all("Secure" in value for value in cookies)


@pytest.mark.asyncio
async def test_cookie_auth_allows_safe_request_and_requires_csrf_for_mutation(client, verified_user):
    login = await _login(client, verified_user)
    csrf_token = login.json()["csrf_token"]

    me = await client.get("/api/v1/auth/me")
    missing = await client.patch("/api/v1/auth/me", json={"name": "Blocked"})
    accepted = await client.patch(
        "/api/v1/auth/me",
        headers={"X-CSRF-Token": csrf_token, "Origin": "http://localhost:3003"},
        json={"name": "Cookie User"},
    )

    assert me.status_code == 200
    assert missing.status_code == 403
    assert missing.json()["detail"] == "csrf_validation_failed"
    assert accepted.status_code == 200
    assert accepted.json()["name"] == "Cookie User"


@pytest.mark.asyncio
async def test_cookie_mutation_rejects_cross_origin_even_with_valid_csrf(client, verified_user):
    login = await _login(client, verified_user)

    response = await client.patch(
        "/api/v1/auth/me",
        headers={"X-CSRF-Token": login.json()["csrf_token"], "Origin": "https://evil.example"},
        json={"name": "Cross Site"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "csrf_origin_invalid"


@pytest.mark.asyncio
async def test_bearer_remains_compatible_and_takes_precedence_over_cookie(client, verified_user, auth_headers):
    await _login(client, verified_user)

    compatible = await client.patch(
        "/api/v1/auth/me",
        headers=auth_headers(verified_user),
        json={"name": "Bearer User"},
    )
    invalid_bearer = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid"},
    )

    assert compatible.status_code == 200
    assert invalid_bearer.status_code == 401


@pytest.mark.asyncio
async def test_reset_token_cannot_authenticate_as_access_token(client, verified_user):
    reset_token = create_reset_token(verified_user.id.hex, verified_user.id, datetime.now(timezone.utc))

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {reset_token}"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout_clears_cookie_session(client, verified_user):
    login = await _login(client, verified_user)

    response = await client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": login.json()["csrf_token"]},
    )
    me = await client.get("/api/v1/auth/me")

    assert response.status_code == 204
    assert client.cookies.get(AUTH_COOKIE_NAME) is None
    assert client.cookies.get(CSRF_COOKIE_NAME) is None
    assert me.status_code == 401


@pytest.mark.asyncio
async def test_cors_preflight_allows_csrf_header(client):
    response = await client.options(
        "/api/v1/auth/me",
        headers={
            "Origin": "http://localhost:3003",
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "X-CSRF-Token",
        },
    )

    assert response.status_code == 200
    assert "x-csrf-token" in response.headers["access-control-allow-headers"].lower()
