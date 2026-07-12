"""Guardrail anti-burn: teto diario de video IA (Seedance) por usuario.

Mesmo com muitos creditos (ex.: conta admin/seed com 999k), nenhum usuario queima $ ilimitado
em video IA num dia. dispatch_pipeline e MagicMock no app de teste -> nao chama Seedance de verdade.
"""

import json
from unittest.mock import MagicMock

import pytest

from app.db.models import User


@pytest.mark.asyncio
async def test_ai_video_daily_cap_blocks_after_limit(client, db_session, verified_user, auth_headers, monkeypatch):
    monkeypatch.setattr("app.api.routes.settings.MAX_AI_VIDEO_PER_DAY", 2)
    user = await db_session.get(User, verified_user.id)
    user.credits = 200  # alto p/ nao esbarrar em 402 (ai_video custa 30)
    await db_session.commit()

    body = {
        "topic": "Curiosidades do oceano profundo",
        "style": "educational",
        "duration_target": 20,
        "template_id": "ai_video",
    }
    r1 = await client.post("/api/v1/generate", headers=auth_headers(verified_user), json=body)
    r2 = await client.post("/api/v1/generate", headers=auth_headers(verified_user), json=body)
    r3 = await client.post("/api/v1/generate", headers=auth_headers(verified_user), json=body)

    assert r1.status_code == 202
    assert r2.status_code == 202
    assert r3.status_code == 429, "3a geracao de video IA no dia deve ser barrada pelo cap diario."

    db_session.expire_all()
    refreshed = await db_session.get(User, verified_user.id)
    assert refreshed.credits == 140, "Cap rejeita ANTES do debito: so 2x30 cobrados (200-60)."


@pytest.mark.asyncio
async def test_non_ai_video_not_capped(client, db_session, verified_user, auth_headers, monkeypatch):
    """Templates normais (stock) nao sofrem o cap de video IA."""
    monkeypatch.setattr("app.api.routes.settings.MAX_AI_VIDEO_PER_DAY", 1)
    user = await db_session.get(User, verified_user.id)
    user.credits = 50
    await db_session.commit()

    body = {
        "topic": "Tema normal de teste",
        "style": "educational",
        "duration_target": 30,
        "template_id": "stock_narration",
    }
    r1 = await client.post("/api/v1/generate", headers=auth_headers(verified_user), json=body)
    r2 = await client.post("/api/v1/generate", headers=auth_headers(verified_user), json=body)
    assert r1.status_code == 202 and r2.status_code == 202, "Stock nao e limitado pelo cap de video IA."


# ── Teto de CENAS específico do ai_video (cada cena = 1 clipe Seedance pago) ──


@pytest.mark.asyncio
async def test_ai_video_custom_script_scene_cap(client, db_session, verified_user, auth_headers):
    """O teto global de cenas (proporcional à duração) permite até 40 a 180s — em
    ai_video isso seria ~R$130 de API por 30 créditos (~R$39). custom_script com
    9+ cenas num template de vídeo IA tem que ser rejeitado (teto próprio de 8)."""
    user = await db_session.get(User, verified_user.id)
    user.credits = 200
    await db_session.commit()

    scenes = [
        {"text": f"Cena numero {i} do roteiro de teste.", "visual_hint": f"cena visual {i}", "duration_hint": 5}
        for i in range(9)
    ]
    body = {
        "topic": "Curiosidades do oceano profundo",
        "style": "educational",
        "duration_target": 180,
        "template_id": "ai_video",
        "custom_script": {"scenes": scenes, "narration": "Texto corrido de teste para narracao."},
    }
    resp = await client.post("/api/v1/generate", headers=auth_headers(verified_user), json=body)
    assert resp.status_code == 422, "9 cenas de video IA = 9 clipes pagos; teto proprio e 8"


@pytest.mark.asyncio
async def test_stock_custom_script_not_capped_at_8(client, db_session, verified_user, auth_headers):
    """O teto apertado é SÓ do ai_video: stock a 180s continua aceitando 12 cenas."""
    user = await db_session.get(User, verified_user.id)
    user.credits = 50
    await db_session.commit()

    scenes = [{"text": f"Cena numero {i} do roteiro de teste."} for i in range(12)]
    body = {
        "topic": "Curiosidades do oceano profundo",
        "style": "educational",
        "duration_target": 180,
        "template_id": "stock_narration",
        "custom_script": {"scenes": scenes, "narration": "Texto corrido de teste para narracao."},
    }
    resp = await client.post("/api/v1/generate", headers=auth_headers(verified_user), json=body)
    assert resp.status_code == 202


def test_scriptwriter_clamps_ai_video_scenes(monkeypatch):
    """LLM que devolve 12 cenas num ai_video de 180s é clampado para 8 (anti-burn
    por template, não só o teto global proporcional à duração)."""
    from app.services import scriptwriter

    fake_script = {
        "topic": "x",
        "narration": "Texto de teste. " * 12,
        "scenes": [{"text": f"Cena {i}.", "visual_hint": f"visual {i}", "duration_hint": 15} for i in range(12)],
    }
    mock = MagicMock(return_value=(json.dumps(fake_script), "openrouter"))
    monkeypatch.setattr(scriptwriter, "complete_text_ex", mock)

    script = scriptwriter.generate_script("tema de teste bem grande", "educational", 180, template_id="ai_video")
    assert len(script["scenes"]) == 8


def test_estimate_api_cost_ai_video_counts_clip_seconds(monkeypatch):
    """Seedance cobra por clipe FIXO de VIDEO_GEN_CLIP_SECONDS por cena — não pelo
    duration_hint (que só guia a narração). Estimar pelos hints distorcia a aba Economia."""
    from app.config import settings
    from app.worker import tasks as worker_tasks

    job_hash = {"template_id": "ai_video", "voice_provider": "edge", "narration_mode": "single", "custom_script": "0"}
    monkeypatch.setattr(worker_tasks, "_redis_hget", lambda _key, field: job_hash.get(field))

    script = {"narration": "abc", "scenes": [{"duration_hint": 12}, {"duration_hint": 12}]}
    cost = worker_tasks._estimate_api_cost_usd("job-x", script)

    expected = (
        settings.API_COST_LLM_PER_CALL_USD
        + settings.API_COST_GROQ_ASR_PER_JOB_USD
        + 2 * settings.VIDEO_GEN_CLIP_SECONDS * settings.API_COST_SEEDANCE_PER_SECOND_USD
    )
    assert abs(cost - round(expected, 4)) < 1e-9, "custo = cenas × clipe de 5s, não soma dos hints (24s)"
