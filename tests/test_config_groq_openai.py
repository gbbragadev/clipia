import os
from unittest.mock import patch

from app.config import Settings


def test_groq_api_key_reads_from_env_var():
    with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_test_123"}, clear=False):
        s = Settings()
    assert s.GROQ_API_KEY == "gsk_test_123"


def test_openai_api_key_reads_from_env_var():
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-proj-test"}, clear=False):
        s = Settings()
    assert s.OPENAI_API_KEY == "sk-proj-test"


def test_asr_fallback_disabled_by_default():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("ASR_FALLBACK_ENABLED", None)
        s = Settings()
    assert s.ASR_FALLBACK_ENABLED is False


def test_asr_fallback_enabled_via_env():
    with patch.dict(os.environ, {"ASR_FALLBACK_ENABLED": "true"}, clear=False):
        s = Settings()
    assert s.ASR_FALLBACK_ENABLED is True
