"""Check offline do diálogo — montagem dos inputs por locutor (puro, sem rede)."""

from app.services.dialogue import build_dialogue_inputs


def test_alterna_vozes_por_speaker():
    scenes = [
        {"speaker": "A", "text": "Oi, sabia disso?"},
        {"speaker": "B", "text": "Não! Conta."},
        {"speaker": "A", "text": "Então..."},
    ]
    out = build_dialogue_inputs(scenes, voice_a="VA", voice_b="VB")
    assert [i["voice_id"] for i in out] == ["VA", "VB", "VA"]
    assert out[0]["text"] == "Oi, sabia disso?"


def test_speaker_ausente_vira_a():
    out = build_dialogue_inputs([{"text": "sem speaker"}], voice_a="VA", voice_b="VB")
    assert out[0]["voice_id"] == "VA"


def test_ignora_falas_vazias():
    out = build_dialogue_inputs([{"speaker": "A", "text": "  "}, {"speaker": "B", "text": "ok"}], "VA", "VB")
    assert len(out) == 1
    assert out[0]["voice_id"] == "VB"


if __name__ == "__main__":
    import sys

    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
