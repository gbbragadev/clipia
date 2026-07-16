import logging

import pytest
from pydantic import SecretStr

from app.config import Settings, validate_production_settings


def _production_settings(**overrides):
    values = {
        "ENVIRONMENT": "production",
        "JWT_SECRET": "j" * 32,
        "METRICS_TOKEN": "m" * 32,
        "FRONTEND_URL": "https://clipia.example",
        "BACKEND_URL": "https://api.clipia.example",
        "CORS_ORIGINS": "https://clipia.example",
        "TRUSTED_HOSTS": "api.clipia.example",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_rejects_default_jwt_secret():
    s = Settings(JWT_SECRET="dev-secret-change-in-production")
    with pytest.raises(ValueError, match="JWT_SECRET"):
        validate_production_settings(s)


def test_rejects_short_jwt_secret():
    s = Settings(JWT_SECRET="abc123")
    with pytest.raises(ValueError, match="JWT_SECRET"):
        validate_production_settings(s)


def test_accepts_strong_jwt_secret():
    s = Settings(JWT_SECRET="a" * 32)
    validate_production_settings(s)  # No exception


def test_warns_missing_api_keys(caplog):
    with caplog.at_level(logging.WARNING):
        s = Settings(
            JWT_SECRET="a" * 32,
            OPEN_ROUTER_API_KEY="",
            PEXELS_API_KEY="",
            GROQ_API_KEY="",
            OPENAI_API_KEY="",
            ELEVENLABS_API_KEY="",
        )
        validate_production_settings(s)
    assert "OPEN_ROUTER_API_KEY" in caplog.text
    assert "GROQ_API_KEY" in caplog.text
    assert "OPENAI_API_KEY" in caplog.text
    assert "ELEVENLABS_API_KEY" in caplog.text


def test_marketing_secrets_are_secretstr_and_never_render_in_repr_or_json_dump():
    raw_values = {
        "MARKETING_EXPORT_TOKEN": "export-" + "x" * 40,
        "MARKETING_PSEUDONYM_SECRET": "pseudonym-" + "y" * 40,
        "META_CAPI_ACCESS_TOKEN": "meta-" + "z" * 40,
    }
    configured = Settings(_env_file=None, **raw_values)

    assert isinstance(configured.MARKETING_EXPORT_TOKEN, SecretStr)
    assert isinstance(configured.MARKETING_PSEUDONYM_SECRET, SecretStr)
    assert isinstance(configured.META_CAPI_ACCESS_TOKEN, SecretStr)
    rendered = repr(configured) + configured.model_dump_json()
    for raw in raw_values.values():
        assert raw not in rendered


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        (
            {"MARKETING_EXPORT_TOKEN": "short", "MARKETING_PSEUDONYM_SECRET": "p" * 32},
            "MARKETING_EXPORT_TOKEN",
        ),
        (
            {"MARKETING_EXPORT_TOKEN": "e" * 32, "MARKETING_PSEUDONYM_SECRET": "short"},
            "MARKETING_PSEUDONYM_SECRET",
        ),
        (
            {
                "META_CAPI_ENABLED": True,
                "META_CAPI_PIXEL_ID": "pixel",
                "META_CAPI_API_VERSION": "v23.0",
                "META_CAPI_ACCESS_TOKEN": "short",
                "MARKETING_PSEUDONYM_SECRET": "p" * 32,
            },
            "META_CAPI_ACCESS_TOKEN",
        ),
    ],
)
def test_production_rejects_short_configured_marketing_secrets(overrides, message):
    with pytest.raises(ValueError, match=message):
        validate_production_settings(_production_settings(**overrides))


def test_production_rejects_incomplete_enabled_meta_capi():
    configured = _production_settings(
        META_CAPI_ENABLED=True,
        META_CAPI_ACCESS_TOKEN="a" * 32,
        MARKETING_PSEUDONYM_SECRET="p" * 32,
        META_CAPI_PIXEL_ID="",
        META_CAPI_API_VERSION="",
    )

    with pytest.raises(ValueError, match="META_CAPI"):
        validate_production_settings(configured)
