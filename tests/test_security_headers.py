import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import create_app


async def _health_headers():
    candidate = create_app()
    async with AsyncClient(transport=ASGITransport(app=candidate), base_url="http://testserver") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    return response.headers


@pytest.mark.asyncio
async def test_security_headers_are_safe_without_claiming_https_in_development(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    headers = await _health_headers()

    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("x-frame-options") == "DENY"
    assert headers.get("x-xss-protection") == "0"
    assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert headers.get("permissions-policy") == "camera=(), microphone=(), geolocation=()"
    assert "strict-transport-security" not in headers
    assert "content-security-policy" not in headers


@pytest.mark.asyncio
async def test_production_adds_hsts_and_restrictive_api_csp(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    headers = await _health_headers()

    assert headers.get("strict-transport-security") == "max-age=31536000; includeSubDomains"
    assert headers.get("content-security-policy") == (
        "default-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    )
