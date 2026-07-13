"""Auditoria 11/07: export (rerender) que falha no worker deve devolver o custo EXATO.

O POST /render debita ceil(pending_credits) e zera o pending; antes destes fixes,
uma falha do worker so marcava "error" e o credito sumia (nem _refund_job_credit,
que devolveria credit_cost — o custo da GERACAO, valor errado). O contrato agora:
a rota grava rerender_cost no hash do job e o worker devolve esse valor em falha.
"""

import pytest

from app.worker import tasks as worker_tasks


@pytest.mark.asyncio
async def test_render_grava_rerender_cost_no_redis(client, verified_user, auth_headers, job_factory, app, storage_dir):
    job = await job_factory(status="completed", pending_credits=1.5)
    (storage_dir / "jobs" / str(job.id)).mkdir(parents=True, exist_ok=True)

    resp = await client.post(f"/api/v1/jobs/{job.id}/render", headers=auth_headers(verified_user))

    assert resp.status_code == 200
    live = app.state.fake_redis.hgetall(f"job:{job.id}")
    assert live["status"] == "rendering"
    assert live["rerender_cost"] == "2", "worker precisa saber o valor exato debitado (ceil(1.5) = 2)"


@pytest.mark.asyncio
async def test_refund_rerender_cost_e_noop_sem_marcador():
    # sem rerender_cost no hash (ex.: job da geracao normal) nada acontece
    worker_tasks._refund_rerender_cost("job-sem-marcador")
    assert worker_tasks._redis.hgetall("job:job-sem-marcador") == {}


@pytest.mark.asyncio
async def test_refund_rerender_cost_nao_perde_valor_se_db_falha(monkeypatch):
    """Dentro de um event loop, asyncio.run() falha (como falharia com DB fora do ar):
    o marcador tem que voltar ao hash e o admin ser alertado — o valor nunca se perde."""
    alerts: list[tuple[str, str]] = []
    monkeypatch.setattr(worker_tasks, "_send_admin_alert", lambda title, body: alerts.append((title, body)))
    worker_tasks._redis.hset("job:job-refund-x", mapping={"rerender_cost": 2})

    refunded = worker_tasks._refund_rerender_cost("job-refund-x")

    assert refunded is False
    assert (
        worker_tasks._redis.hget("job:job-refund-x", "rerender_cost") == "2"
    ), "falha no refund deve restaurar o marcador para reconciliacao"
    assert alerts, "falha no refund deve alertar o admin (antes era 100% silenciosa)"
    assert "reembolsar manualmente" not in alerts[0][1].lower()


@pytest.mark.asyncio
async def test_ai_suggest_concorrente_retorna_429(client, verified_user, auth_headers, job_factory, app):
    """Duas chamadas paralelas de ai-suggest duplicavam o custo de LLM (chamada fora de
    lock por 15-40s). Com o SETNX inflight, a segunda leva 429 em vez de pagar de novo."""
    job = await job_factory(status="completed", script={"scenes": [{"text": "oi", "duration_hint": 7}]})
    app.state.fake_redis.set(f"ai_suggest:{job.id}:inflight", "1")

    resp = await client.post(
        f"/api/v1/jobs/{job.id}/ai-suggest",
        headers=auth_headers(verified_user),
        json={"message": "melhora a cena 1"},
    )

    assert resp.status_code == 429
