"""Regressao (auditoria go-live 04/07): o credito debitado DEVE ser estornado se o
enfileiramento da task Celery falhar (broker/Redis down). Sem isso, o usuario paga e o
job nunca roda — perda silenciosa de dinheiro. Achados criticos em /generate e /render."""

import pytest

import app.api.routes as api_routes
from app.db.models import User


@pytest.mark.asyncio
async def test_generate_refunds_credit_when_dispatch_fails(client, verified_user, auth_headers, monkeypatch, test_db):
    def boom(*_a, **_k):
        raise RuntimeError("Celery broker offline")

    monkeypatch.setattr(api_routes, "dispatch_pipeline", boom)
    before = verified_user.credits

    resp = await client.post(
        "/api/v1/generate",
        headers=auth_headers(verified_user),
        json={"topic": "um tema qualquer bem valido", "style": "educational", "duration_target": 30},
    )

    assert resp.status_code == 503
    async with test_db["session_factory"]() as s:
        fresh = await s.get(User, verified_user.id)
    assert fresh.credits == before, "credito deveria ter sido estornado apos falha de enfileiramento"


@pytest.mark.asyncio
async def test_render_refunds_credit_when_enqueue_fails(
    client, verified_user, auth_headers, job_factory, monkeypatch, test_db, storage_dir
):
    job = await job_factory(status="completed", pending_credits=1.0)
    (storage_dir / "jobs" / str(job.id)).mkdir(parents=True, exist_ok=True)

    from app.worker import tasks as worker_tasks

    def boom(*_a, **_k):
        raise RuntimeError("Celery broker offline")

    monkeypatch.setattr(worker_tasks.task_rerender_video, "delay", boom)
    before = verified_user.credits

    resp = await client.post(f"/api/v1/jobs/{job.id}/render", headers=auth_headers(verified_user))

    assert resp.status_code == 503
    async with test_db["session_factory"]() as s:
        fresh = await s.get(User, verified_user.id)
    assert fresh.credits == before, "credito deveria ter sido estornado apos falha de enfileiramento do render"
