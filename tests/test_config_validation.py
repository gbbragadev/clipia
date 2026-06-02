import logging

import pytest

from app.config import Settings, validate_production_settings


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
