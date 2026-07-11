"""F2 (reforma UX 2026-07-10): rota publica /config e thumbnail autenticado por job."""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException

from app.api import routes as api_routes
from app.config import settings
from tests.voice_test_support import create_job, create_test_env, run


def test_public_config_expoe_valores_de_oferta():
    response = run(api_routes.public_config())
    # Guardrail de confianca: a UI le esses numeros daqui, nunca hardcoda.
    assert response["welcome_credit_bonus"] == settings.WELCOME_CREDIT_BONUS
    assert response["purchase_bonus_percent"] == settings.PURCHASE_BONUS_PERCENT


def test_thumbnail_404_sem_arquivo(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)
    job = create_job(env, status="completed")

    async def _case():
        async with env.session_factory() as db:
            return await api_routes.job_thumbnail(job_id=str(job.id), user=env.verified_user, db=db)

    try:
        run(_case())
        raise AssertionError("esperava 404 sem thumbnail no disco")
    except HTTPException as exc:
        assert exc.status_code == 404


def test_thumbnail_servido_quando_existe(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)
    job = create_job(env, status="completed")
    output_dir = Path(settings.STORAGE_DIR) / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"{job.id}.jpg").write_bytes(b"\xff\xd8\xff jpeg fake")

    async def _case():
        async with env.session_factory() as db:
            return await api_routes.job_thumbnail(job_id=str(job.id), user=env.verified_user, db=db)

    response = run(_case())
    assert response.media_type == "image/jpeg"

    # E o list_jobs passa a anunciar a thumbnail_url do job.
    async def _list():
        async with env.session_factory() as db:
            return await api_routes.list_jobs(user=env.verified_user, db=db)

    listed = next(item for item in run(_list()) if item["job_id"] == str(job.id))
    assert listed["thumbnail_url"] == f"/api/v1/jobs/{job.id}/thumbnail"
