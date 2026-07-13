from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings, settings, validate_production_settings
from app.main import create_app


def _production_settings(**overrides) -> Settings:
    values = {
        "ENVIRONMENT": "production",
        "JWT_SECRET": "a" * 32,
        "CORS_ORIGINS": "https://clipia.com.br",
        "TRUSTED_HOSTS": "api.clipia.com.br,testserver",
        "METRICS_TOKEN": "m" * 32,
        "FRONTEND_URL": "https://clipia.com.br",
        "BACKEND_URL": "https://api.clipia.com.br",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"CORS_ORIGINS": "*"}, "CORS_ORIGINS"),
        ({"TRUSTED_HOSTS": "*"}, "TRUSTED_HOSTS"),
        ({"METRICS_TOKEN": "short"}, "METRICS_TOKEN"),
        ({"FRONTEND_URL": "http://clipia.com.br"}, "FRONTEND_URL"),
        ({"BACKEND_URL": "http://api.clipia.com.br"}, "BACKEND_URL"),
        ({"CORS_ORIGINS": "https://outro.example"}, "CORS_ORIGINS"),
        ({"TRUSTED_HOSTS": "outro.example"}, "TRUSTED_HOSTS"),
    ],
)
def test_production_settings_reject_insecure_infrastructure(override, message):
    with pytest.raises(ValueError, match=message):
        validate_production_settings(_production_settings(**override))


@pytest.mark.asyncio
async def test_production_hides_docs_protects_metrics_hosts_and_sets_csp(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production", raising=False)
    monkeypatch.setattr(settings, "TRUSTED_HOSTS", "api.clipia.com.br,testserver", raising=False)
    monkeypatch.setattr(settings, "CORS_ORIGINS", "https://clipia.com.br")
    monkeypatch.setattr(settings, "METRICS_TOKEN", "m" * 32, raising=False)
    monkeypatch.setattr("app.main.render_metrics", AsyncMock(return_value="# secure\n"))

    production_app = create_app()
    transport = ASGITransport(app=production_app, client=("127.0.0.1", 50000))
    async with AsyncClient(transport=transport, base_url="https://testserver") as client:
        docs = await client.get("/docs")
        schema = await client.get("/openapi.json")
        unauthorized_metrics = await client.get("/metrics")
        authorized_metrics = await client.get("/metrics", headers={"Authorization": f"Bearer {'m' * 32}"})
        health = await client.get("/health")
        untrusted = await client.get("/health", headers={"Host": "evil.example"})

    assert docs.status_code == 404
    assert schema.status_code == 404
    assert unauthorized_metrics.status_code == 401
    assert authorized_metrics.status_code == 200
    assert authorized_metrics.text == "# secure\n"
    assert health.headers["content-security-policy"] == (
        "default-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    )
    assert health.headers["strict-transport-security"].startswith("max-age=31536000")
    assert untrusted.status_code == 400
