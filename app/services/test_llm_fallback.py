"""Check do fallback LLM: se o modelo principal falha, tenta o FREE de fallback."""

import pytest

import app.services.llm as llm
from app.config import settings


def test_fallback_quando_principal_falha(monkeypatch):
    calls = []

    def fake_call(model, prompt, max_tokens, json_mode):
        calls.append(model)
        if model == settings.LLM_MODEL:
            raise RuntimeError("403 Key limit exceeded")
        return '{"ok": true}'

    monkeypatch.setattr(llm, "_call", fake_call)
    assert llm.complete_text("gere algo") == '{"ok": true}'
    assert calls == [settings.LLM_MODEL, settings.LLM_FALLBACK_MODEL]


def test_sem_fallback_propaga_erro(monkeypatch):
    monkeypatch.setattr(settings, "LLM_FALLBACK_MODEL", "")
    monkeypatch.setattr(llm, "_call", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        llm.complete_text("x")


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-q"]))
