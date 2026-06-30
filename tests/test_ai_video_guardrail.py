"""Guardrail anti-burn: teto diario de video IA (Seedance) por usuario.

Mesmo com muitos creditos (ex.: conta admin/seed com 999k), nenhum usuario queima $ ilimitado
em video IA num dia. dispatch_pipeline e MagicMock no app de teste -> nao chama Seedance de verdade.
"""

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

    assert r1.status_code == 200
    assert r2.status_code == 200
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
    assert r1.status_code == 200 and r2.status_code == 200, "Stock nao e limitado pelo cap de video IA."
