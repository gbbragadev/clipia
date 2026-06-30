"""Cascata de provedores LLM: OpenRouter pago -> OpenAI -> xAI -> OpenRouter free.

complete_text tenta cada provedor em ordem e retorna a primeira resposta nao-vazia.
"""

import pytest

import app.services.llm as llm
from app.config import settings


def _only_openrouter(monkeypatch):
    """Restringe a cascata a OpenRouter (pago + free), limpando OpenAI/xAI."""
    monkeypatch.setattr(settings, "OPEN_ROUTER_API_KEY", "or-key")
    monkeypatch.setattr(settings, "LLM_OPENAI_KEY", "")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "LLM_XAI_KEY", "")


def test_cascata_pula_provedor_que_falha(monkeypatch):
    _only_openrouter(monkeypatch)
    calls = []

    def fake_call(model, prompt, max_tokens, json_mode, base_url, api_key):
        calls.append(model)
        if model == settings.LLM_MODEL:
            raise RuntimeError("402 Insufficient credits")
        return '{"ok": true}'

    monkeypatch.setattr(llm, "_call", fake_call)
    assert llm.complete_text("gere algo") == '{"ok": true}'
    assert calls == [settings.LLM_MODEL, settings.LLM_FALLBACK_MODEL]


def test_cascata_openai_primario(monkeypatch):
    """30/06: OpenAI e o provedor PRIMARIO (OpenRouter pago zerou)."""
    monkeypatch.setattr(settings, "OPEN_ROUTER_API_KEY", "or-key")
    monkeypatch.setattr(settings, "LLM_OPENAI_KEY", "sk-test")
    monkeypatch.setattr(settings, "LLM_OPENAI_MODEL", "gpt-4o-mini")
    monkeypatch.setattr(settings, "LLM_XAI_KEY", "")
    calls = []

    def fake_call(model, prompt, max_tokens, json_mode, base_url, api_key):
        calls.append((model, base_url))
        if model == "gpt-4o-mini":
            return '{"scenes": [1]}'
        return ""

    monkeypatch.setattr(llm, "_call", fake_call)
    assert llm.complete_text("x") == '{"scenes": [1]}'
    assert calls[0] == ("gpt-4o-mini", settings.OPENAI_BASE_URL), "OpenAI deve ser tentado PRIMEIRO."


def test_todos_vazios_levanta(monkeypatch):
    _only_openrouter(monkeypatch)
    monkeypatch.setattr(llm, "_call", lambda *a, **k: "")
    with pytest.raises((ValueError, RuntimeError)):
        llm.complete_text("x")


def test_sem_provedor_configurado_levanta(monkeypatch):
    monkeypatch.setattr(settings, "OPEN_ROUTER_API_KEY", "")
    monkeypatch.setattr(settings, "LLM_OPENAI_KEY", "")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "LLM_XAI_KEY", "")
    with pytest.raises(RuntimeError):
        llm.complete_text("x")


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-q"]))
