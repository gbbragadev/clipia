"""Rascunho de roteiro: preview grátis, refino 0,5cr acumulado e custom_script no /generate."""

import json
from unittest.mock import MagicMock

import pytest
from sqlalchemy import update

from app.db.models import User

VALID_SCRIPT = {
    "title": "Teste",
    "narration": "Primeira cena. Segunda cena.",
    "scenes": [
        {"text": "Primeira cena.", "keywords_en": ["ocean"], "duration_hint": 15},
        {"text": "Segunda cena.", "keywords_en": ["deep sea"], "duration_hint": 15},
    ],
    "hashtags": ["#shorts"],
}

BASE_BODY = {
    "topic": "cinco curiosidades sobre o oceano profundo",
    "style": "educational",
    "duration_target": 30,
    "template_id": "stock_narration",
    "voice_provider": "edge",
}


def _mock_scriptwriter(monkeypatch):
    monkeypatch.setattr(
        "app.services.scriptwriter.complete_text_ex",
        MagicMock(return_value=(json.dumps(VALID_SCRIPT), "openrouter")),
    )


@pytest.mark.asyncio
async def test_preview_is_free_and_returns_script(client, verified_user, auth_headers, monkeypatch, db_session):
    _mock_scriptwriter(monkeypatch)
    credits_before = verified_user.credits

    resp = await client.post("/api/v1/script-preview", json=BASE_BODY, headers=auth_headers(verified_user))

    assert resp.status_code == 200
    body = resp.json()
    assert body["script"]["scenes"]
    assert body["refine_cost"] == 0.5
    fresh = await db_session.get(User, verified_user.id)
    assert fresh.credits == credits_before  # 1º rascunho é incluso: não debita


@pytest.mark.asyncio
async def test_preview_requires_enough_balance_for_template(
    client, app, verified_user, auth_headers, db_session, monkeypatch
):
    """Anti-farming: sem saldo para gerar o vídeo, não há preview grátis."""
    _mock_scriptwriter(monkeypatch)
    await db_session.execute(update(User).where(User.id == verified_user.id).values(credits=0))
    await db_session.commit()

    resp = await client.post("/api/v1/script-preview", json=BASE_BODY, headers=auth_headers(verified_user))

    assert resp.status_code == 402


@pytest.mark.asyncio
async def test_refine_accumulates_half_credit(client, app, verified_user, auth_headers, monkeypatch):
    _mock_scriptwriter(monkeypatch)

    body = {
        "script": VALID_SCRIPT,
        "instruction": "deixe a cena 2 mais dramática",
        "duration_target": 30,
        "template_id": "stock_narration",
    }
    r1 = await client.post("/api/v1/script-preview/refine", json=body, headers=auth_headers(verified_user))
    assert r1.status_code == 200
    assert r1.json()["refine_pending"] == 0.5

    r2 = await client.post("/api/v1/script-preview/refine", json=body, headers=auth_headers(verified_user))
    assert r2.json()["refine_pending"] == 1.0


@pytest.mark.asyncio
async def test_generate_settles_whole_refines_and_carries_remainder(
    client, app, verified_user, auth_headers, db_session
):
    """1,5 pendente: o /generate cobra base+1 e carrega 0,5 (nunca cobra a mais)."""
    fake = app.state.fake_redis
    fake.set(f"script_refine_pending:{verified_user.id}", "1.5")
    credits_before = verified_user.credits

    resp = await client.post("/api/v1/generate", json=BASE_BODY, headers=auth_headers(verified_user))

    assert resp.status_code == 202
    assert resp.json()["credit_cost"] == 2  # 1 do template + 1 inteiro dos refinos
    fresh = await db_session.get(User, verified_user.id)
    assert fresh.credits == credits_before - 2
    assert fake.get(f"script_refine_pending:{verified_user.id}") == "0.5"  # meio carrega


@pytest.mark.asyncio
async def test_generate_with_half_refine_charges_base_only(client, app, verified_user, auth_headers, db_session):
    fake = app.state.fake_redis
    fake.set(f"script_refine_pending:{verified_user.id}", "0.5")

    resp = await client.post("/api/v1/generate", json=BASE_BODY, headers=auth_headers(verified_user))

    assert resp.status_code == 202
    assert resp.json()["credit_cost"] == 1  # floor(0.5) = 0: nada a liquidar ainda
    assert fake.get(f"script_refine_pending:{verified_user.id}") == "0.5"


@pytest.mark.asyncio
async def test_generate_with_custom_script_writes_script_json(client, app, verified_user, auth_headers, test_db):
    resp = await client.post(
        "/api/v1/generate",
        json={**BASE_BODY, "custom_script": VALID_SCRIPT},
        headers=auth_headers(verified_user),
    )

    assert resp.status_code == 202
    job_id = resp.json()["job_id"]
    script_path = test_db["storage_dir"] / "jobs" / job_id / "script.json"
    assert script_path.exists()
    saved = json.loads(script_path.read_text(encoding="utf-8"))
    assert saved["narration"] == VALID_SCRIPT["narration"]
    assert app.state.fake_redis.hget(f"job:{job_id}", "custom_script") == "1"


@pytest.mark.asyncio
async def test_generate_rejects_malformed_custom_script(client, verified_user, auth_headers):
    resp = await client.post(
        "/api/v1/generate",
        json={**BASE_BODY, "custom_script": {"scenes": [], "narration": ""}},
        headers=auth_headers(verified_user),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_custom_script_enforces_scene_cap_anti_burn(client, verified_user, auth_headers):
    """O caminho custom pula o generate_script, mas o teto anti-burn vale igual:
    20 cenas num template de imagem IA seriam 20 geracoes PAGAS."""
    bloated = {
        "narration": "x " * 40,
        "scenes": [{"text": f"cena {i} com texto valido", "duration_hint": 3} for i in range(20)],
    }
    resp = await client.post(
        "/api/v1/generate",
        json={**BASE_BODY, "duration_target": 30, "custom_script": bloated},
        headers=auth_headers(verified_user),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_custom_script_requires_visual_hint_when_template_demands(client, verified_user, auth_headers):
    no_hint = {
        "narration": "Uma cena sem hint.",
        "scenes": [{"text": "Uma cena sem hint.", "duration_hint": 30}],
    }
    resp = await client.post(
        "/api/v1/generate",
        json={
            **BASE_BODY,
            "template_id": "novelinha_historica",
            "voice_provider": "elevenlabs",
            "custom_script": no_hint,
        },
        headers=auth_headers(verified_user),
    )
    assert resp.status_code == 422


def test_custom_script_normalizes_dialogue_speakers():
    from app.models import GenerateRequest

    req = GenerateRequest(
        topic="tema de teste com dialogo",
        template_id="stock_narration",
        narration_mode="dialogue",
        custom_script={
            "narration": "Oi. Olá.",
            "scenes": [
                {"text": "Oi.", "speaker": "b"},
                {"text": "Olá.", "speaker": "invalido"},
            ],
        },
    )
    assert [sc["speaker"] for sc in req.custom_script["scenes"]] == ["B", "A"]


@pytest.mark.asyncio
async def test_preview_rate_limited_per_hour(client, verified_user, auth_headers, monkeypatch, app):
    _mock_scriptwriter(monkeypatch)
    from app.api import routes as api_routes

    monkeypatch.setattr(api_routes, "_SCRIPT_PREVIEW_HOURLY_CAP", 2)

    h = auth_headers(verified_user)
    assert (await client.post("/api/v1/script-preview", json=BASE_BODY, headers=h)).status_code == 200
    assert (await client.post("/api/v1/script-preview", json=BASE_BODY, headers=h)).status_code == 200
    assert (await client.post("/api/v1/script-preview", json=BASE_BODY, headers=h)).status_code == 429
