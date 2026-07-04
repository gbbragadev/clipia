"""Status em tempo real dos jobs: corrida do export e grid reativa.

Bug raiz do export: POST /render enfileirava o re-render mas NAO tocava o Redis;
entre o POST e o worker (--pool=solo, fila pode estar ocupada) o /status devolvia
o "completed" estale do pipeline original e o editor liberava o download da versao
pre-edicao.
"""

import pytest


@pytest.mark.asyncio
async def test_render_marks_redis_rendering_before_worker_starts(
    client, app, job_factory, verified_user, auth_headers, storage_dir
):
    job = await job_factory(status="completed")
    fake_redis = app.state.fake_redis
    # Estado estale do pipeline original (worker ainda nao pegou o re-render).
    fake_redis.hset(f"job:{job.id}", mapping={"status": "completed", "progress": 1.0})
    (storage_dir / "jobs" / str(job.id)).mkdir(parents=True)

    resp = await client.post(f"/api/v1/jobs/{job.id}/render", headers=auth_headers(verified_user))

    assert resp.status_code == 200
    data = fake_redis.hgetall(f"job:{job.id}")
    assert data["status"] == "rendering", (
        "POST /render deve marcar 'rendering' sincronamente; sem isso o poll do editor "
        "le 'completed' estale e libera o download da versao pre-edicao."
    )
    app.state.rerender_task.delay.assert_called_once_with(str(job.id))

    status = await client.get(f"/api/v1/jobs/{job.id}/status", headers=auth_headers(verified_user))
    assert status.status_code == 200
    assert status.json()["status"] == "rendering"


@pytest.mark.asyncio
async def test_list_jobs_exposes_realtime_progress(client, app, job_factory, verified_user, auth_headers):
    """Grid reativa: /jobs devolve progress/current_step do Redis para o card mostrar
    a etapa atual sem F5 (antes o hash era lido e os campos descartados)."""
    job = await job_factory(status="processing")
    app.state.fake_redis.hset(
        f"job:{job.id}",
        mapping={"status": "processing", "progress": 0.45, "current_step": "transcribing"},
    )

    resp = await client.get("/api/v1/jobs", headers=auth_headers(verified_user))

    assert resp.status_code == 200
    item = next(i for i in resp.json() if i["job_id"] == str(job.id))
    assert item["status"] == "processing"
    assert item["progress"] == pytest.approx(0.45)
    assert item["current_step"] == "transcribing"


@pytest.mark.asyncio
async def test_list_jobs_without_redis_hash_defaults_progress(client, job_factory, verified_user, auth_headers):
    """Job antigo sem hash no Redis (expirou): progress 0 e step None, sem quebrar."""
    job = await job_factory(status="completed")

    resp = await client.get("/api/v1/jobs", headers=auth_headers(verified_user))

    assert resp.status_code == 200
    item = next(i for i in resp.json() if i["job_id"] == str(job.id))
    assert item["progress"] == 0.0
    assert item["current_step"] is None
