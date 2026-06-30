"""Testes para complete_text: cascata de provedores (fallback por exceção E por resposta vazia)."""

from unittest.mock import patch

import pytest

from app.config import settings
from app.services.llm import complete_text


def _only_openrouter(monkeypatch):
    """Restringe a cascata a OpenRouter (pago + free), limpando OpenAI/xAI."""
    monkeypatch.setattr(settings, "OPEN_ROUTER_API_KEY", "or-key")
    monkeypatch.setattr(settings, "LLM_OPENAI_KEY", "")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "LLM_XAI_KEY", "")


def _patch_call(main_return=None, main_exc=None, fallback_return="fallback ok"):
    """Helper: patch _call (nova assinatura) com comportamentos distintos por modelo."""

    def fake_call(model, prompt, max_tokens, json_mode, base_url, api_key):
        if model == settings.LLM_MODEL:
            if main_exc:
                raise main_exc
            return main_return
        return fallback_return

    return patch("app.services.llm._call", side_effect=fake_call)


def test_returns_main_result_when_non_empty(monkeypatch):
    _only_openrouter(monkeypatch)
    with _patch_call(main_return="resultado ok"):
        assert complete_text("prompt") == "resultado ok"


def test_fallback_on_exception(monkeypatch):
    _only_openrouter(monkeypatch)
    with _patch_call(main_exc=RuntimeError("quota"), fallback_return="fallback ok"):
        assert complete_text("prompt") == "fallback ok"


def test_fallback_on_empty_response(monkeypatch):
    """Reasoning exauriu max_tokens -> resposta vazia -> deve acionar o proximo provedor."""
    _only_openrouter(monkeypatch)
    with _patch_call(main_return="", fallback_return="fallback ok"):
        assert complete_text("prompt") == "fallback ok"


def test_raises_when_no_fallback_configured(monkeypatch):
    _only_openrouter(monkeypatch)
    monkeypatch.setattr(settings, "LLM_FALLBACK_MODEL", "")
    with _patch_call(main_return=""):
        with pytest.raises((ValueError, RuntimeError)):
            complete_text("prompt")
