"""Testes para complete_text: fallback por exceção E por resposta vazia."""

from unittest.mock import patch

import pytest

from app.services.llm import complete_text


def _patch_call(main_return=None, main_exc=None, fallback_return="fallback ok"):
    """Helper: patch _call com comportamentos distintos por modelo."""
    model_map = {}
    if main_exc:
        model_map["main"] = main_exc
    else:
        model_map["main"] = main_return

    def fake_call(model, prompt, max_tokens, json_mode):
        if model == "deepseek/deepseek-v4-pro":
            if isinstance(model_map["main"], Exception):
                raise model_map["main"]
            return model_map["main"]
        return fallback_return

    return patch("app.services.llm._call", side_effect=fake_call)


def test_returns_main_result_when_non_empty():
    with _patch_call(main_return="resultado ok"):
        assert complete_text("prompt") == "resultado ok"


def test_fallback_on_exception(monkeypatch):
    monkeypatch.setattr("app.services.llm.settings.LLM_MODEL", "deepseek/deepseek-v4-pro")
    monkeypatch.setattr("app.services.llm.settings.LLM_FALLBACK_MODEL", "free/model")
    with _patch_call(main_exc=RuntimeError("quota"), fallback_return="fallback ok"):
        assert complete_text("prompt") == "fallback ok"


def test_fallback_on_empty_response(monkeypatch):
    """Reasoning exauriu max_tokens → resposta vazia → deve acionar fallback."""
    monkeypatch.setattr("app.services.llm.settings.LLM_MODEL", "deepseek/deepseek-v4-pro")
    monkeypatch.setattr("app.services.llm.settings.LLM_FALLBACK_MODEL", "free/model")
    with _patch_call(main_return="", fallback_return="fallback ok"):
        assert complete_text("prompt") == "fallback ok"


def test_raises_when_no_fallback_configured(monkeypatch):
    monkeypatch.setattr("app.services.llm.settings.LLM_MODEL", "deepseek/deepseek-v4-pro")
    monkeypatch.setattr("app.services.llm.settings.LLM_FALLBACK_MODEL", "")
    with _patch_call(main_return=""):
        with pytest.raises(ValueError, match="resposta vazia"):
            complete_text("prompt")
