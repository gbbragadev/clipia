"""Matriz template × narração: modo diálogo (2 vozes) desacoplado do template dialogue_duo."""

import json
from unittest.mock import MagicMock

import pytest

from app.templates import TEMPLATES

DIALOGUE_JSON = {
    "topic": "cinco curiosidades sobre o oceano profundo",
    "style": "educational",
    "duration_target": 30,
    "voice_provider": "edge",
    "narration_mode": "dialogue",
}


@pytest.mark.asyncio
async def test_dialogue_on_capable_template_charges_elevenlabs(client, app, verified_user, auth_headers):
    """Diálogo sintetiza com 2 vozes ElevenLabs: o custo é o pricing elevenlabs do
    template, decidido server-side mesmo com voice_provider=edge no request."""
    resp = await client.post(
        "/api/v1/generate",
        json={**DIALOGUE_JSON, "template_id": "stock_narration"},
        headers=auth_headers(verified_user),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["credit_cost"] == 2  # elevenlabs pricing (edge seria 1)
    assert app.state.fake_redis.hget(f"job:{body['job_id']}", "narration_mode") == "dialogue"


@pytest.mark.asyncio
async def test_dialogue_on_incapable_template_is_rejected(client, verified_user, auth_headers):
    resp = await client.post(
        "/api/v1/generate",
        json={**DIALOGUE_JSON, "template_id": "gameplay_split"},
        headers=auth_headers(verified_user),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_single_mode_still_charges_selected_provider(client, verified_user, auth_headers):
    resp = await client.post(
        "/api/v1/generate",
        json={
            "topic": "cinco curiosidades sobre o oceano profundo",
            "style": "educational",
            "duration_target": 30,
            "template_id": "stock_narration",
            "voice_provider": "edge",
        },
        headers=auth_headers(verified_user),
    )
    assert resp.status_code == 200
    assert resp.json()["credit_cost"] == 1


def test_dialogue_capable_curation():
    """Curadoria explícita: 5 formatos aceitam diálogo; dialogue_duo é nativo (sem toggle)."""
    capable = {tid for tid, t in TEMPLATES.items() if t.dialogue_capable}
    assert capable == {"stock_narration", "curiosidades_lista", "story_time", "novelinha_historica", "ai_visual"}
    assert TEMPLATES["dialogue_duo"].script.is_dialogue
    assert not TEMPLATES["dialogue_duo"].dialogue_capable


def test_force_dialogue_builds_dialogue_script(monkeypatch):
    """force_dialogue liga o roteiro em conversa num template que NÃO é diálogo nativo:
    o prompt ganha a instrução de speaker e as cenas saem normalizadas em A/B."""
    from app.services import scriptwriter

    fake_script = {
        "topic": "x",
        "narration": "A: Olá. B: Oi, tudo bem?",
        "scenes": [
            {"text": "Olá.", "speaker": "a", "duration_hint": 5},
            {"text": "Oi, tudo bem?", "speaker": "b", "duration_hint": 5},
        ],
    }
    mock = MagicMock(return_value=(json.dumps(fake_script), "openrouter"))
    monkeypatch.setattr(scriptwriter, "complete_text_ex", mock)

    script = scriptwriter.generate_script(
        "tema de teste com diálogo", "educational", 30, template_id="stock_narration", force_dialogue=True
    )

    prompt_sent = mock.call_args.args[0]
    assert "speaker" in prompt_sent  # instrução de diálogo entrou no prompt
    assert [sc["speaker"] for sc in script["scenes"]] == ["A", "B"]


def test_without_force_dialogue_no_speaker_instruction(monkeypatch):
    from app.services import scriptwriter

    fake_script = {
        "topic": "x",
        "narration": "Texto corrido.",
        "scenes": [{"text": "Texto corrido.", "duration_hint": 5}],
    }
    mock = MagicMock(return_value=(json.dumps(fake_script), "openrouter"))
    monkeypatch.setattr(scriptwriter, "complete_text_ex", mock)

    scriptwriter.generate_script("tema de teste sem diálogo", "educational", 30, template_id="stock_narration")

    prompt_sent = mock.call_args.args[0]
    assert '"speaker"' not in prompt_sent
