from __future__ import annotations

import importlib
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from app.api import routes as api_routes
from app.db.models import Job, User
from app.services import job_operations
from app.worker import tasks as worker_tasks
from app.worker.celery_app import celery_app
from tests.voice_test_support import create_job, create_test_env, run


def _generate_payload() -> dict:
    return {
        "topic": "Tema valido para testar compensacao de dispatch",
        "style": "educational",
        "duration_target": 30,
        "custom_script": {
            "narration": "Uma narracao valida para o roteiro customizado.",
            "scenes": [{"text": "Cena inicial", "duration_hint": 5}],
        },
    }


@pytest.mark.asyncio
async def test_generate_initial_redis_failure_refunds_and_restores_refine_snapshot(
    client,
    verified_user,
    auth_headers,
    app,
    test_db,
    storage_dir: Path,
    monkeypatch,
):
    refine_key = f"script_refine_pending:{verified_user.id}"
    app.state.fake_redis.set(refine_key, "1.5", ex=86400)
    original_hset = app.state.fake_redis.hset
    calls = 0

    def fail_initial_hset(key: str, mapping: dict[str, str]):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("redis unavailable")
        return original_hset(key, mapping)

    monkeypatch.setattr(app.state.fake_redis, "hset", fail_initial_hset)

    response = await client.post(
        "/api/v1/generate",
        headers=auth_headers(verified_user),
        json=_generate_payload(),
    )

    assert response.status_code == 503
    async with test_db["session_factory"]() as session:
        user = await session.get(User, verified_user.id)
        job = (await session.execute(select(Job).where(Job.user_id == verified_user.id))).scalar_one()
    assert user.credits == 5
    assert job.status == "failed"
    assert job.generation_refunded_at is not None
    assert app.state.fake_redis.get(refine_key) == "1.5"
    assert not (storage_dir / "jobs" / str(job.id)).exists()
    app.state.dispatch_pipeline.assert_not_called()


@pytest.mark.asyncio
async def test_generate_dispatch_failure_refunds_and_cleans_custom_script(
    client,
    verified_user,
    auth_headers,
    app,
    test_db,
    storage_dir: Path,
):
    app.state.dispatch_pipeline.side_effect = RuntimeError("broker unavailable")

    response = await client.post(
        "/api/v1/generate",
        headers=auth_headers(verified_user),
        json=_generate_payload(),
    )

    assert response.status_code == 503
    async with test_db["session_factory"]() as session:
        user = await session.get(User, verified_user.id)
        job = (await session.execute(select(Job).where(Job.user_id == verified_user.id))).scalar_one()
    assert user.credits == 5
    assert job.status == "failed"
    assert job.generation_refunded_at is not None
    assert not (storage_dir / "jobs" / str(job.id)).exists()


@pytest.mark.asyncio
async def test_generate_marker_failure_after_broker_acceptance_does_not_refund(
    client,
    verified_user,
    auth_headers,
    app,
    test_db,
    monkeypatch,
):
    async def fail_marker(*_args, **_kwargs):
        raise RuntimeError("database unavailable after dispatch")

    monkeypatch.setattr(api_routes, "mark_generation_dispatched", fail_marker)

    response = await client.post(
        "/api/v1/generate",
        headers=auth_headers(verified_user),
        json=_generate_payload(),
    )

    assert response.status_code == 202
    async with test_db["session_factory"]() as session:
        user = await session.get(User, verified_user.id)
        job = (await session.execute(select(Job).where(Job.user_id == verified_user.id))).scalar_one()
    assert user.credits == 4
    assert job.status == "queued"
    assert job.generation_refunded_at is None
    assert job.generation_dispatched_at is None
    app.state.dispatch_pipeline.assert_called_once()


@pytest.mark.asyncio
async def test_generate_custom_script_write_failure_happens_before_debit(
    client,
    verified_user,
    auth_headers,
    app,
    test_db,
    monkeypatch,
):
    original_write_text = Path.write_text

    def fail_script_write(path: Path, *args, **kwargs):
        if path.name == "script.json":
            raise OSError("storage read-only")
        return original_write_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_script_write)

    response = await client.post(
        "/api/v1/generate",
        headers=auth_headers(verified_user),
        json=_generate_payload(),
    )

    assert response.status_code == 503
    async with test_db["session_factory"]() as session:
        user = await session.get(User, verified_user.id)
        jobs = (await session.execute(select(Job).where(Job.user_id == verified_user.id))).scalars().all()
    assert user.credits == 5
    assert jobs == []
    app.state.dispatch_pipeline.assert_not_called()


@pytest.mark.asyncio
async def test_generate_quota_reservation_failure_happens_before_debit(
    client,
    verified_user,
    auth_headers,
    app,
    test_db,
    monkeypatch,
):
    monkeypatch.setattr(api_routes.settings, "MAX_AI_VIDEO_PER_DAY", 2)
    monkeypatch.setattr(app.state.fake_redis, "incr", lambda _key: (_ for _ in ()).throw(RuntimeError("redis down")))
    payload = _generate_payload()
    payload["template_id"] = "ai_video"
    payload.pop("custom_script")

    response = await client.post("/api/v1/generate", headers=auth_headers(verified_user), json=payload)

    assert response.status_code == 503
    async with test_db["session_factory"]() as session:
        user = await session.get(User, verified_user.id)
        jobs = (await session.execute(select(Job).where(Job.user_id == verified_user.id))).scalars().all()
    assert user.credits == 5
    assert jobs == []
    app.state.dispatch_pipeline.assert_not_called()


@pytest.mark.asyncio
async def test_generate_snapshots_refine_balance_inside_user_lock(
    client,
    verified_user,
    auth_headers,
    app,
    monkeypatch,
):
    locked = False
    original_get = app.state.fake_redis.get

    class RecordingLock:
        async def __aenter__(self):
            nonlocal locked
            locked = True

        async def __aexit__(self, *_args):
            nonlocal locked
            locked = False

    def guarded_get(key: str):
        if key.startswith("script_refine_pending:"):
            assert locked, "refine snapshot must be serialized with debit and mutation"
        return original_get(key)

    def guarded_dispatch(*_args, **_kwargs):
        assert locked, "dispatch compensation must remain serialized with its refine snapshot"

    monkeypatch.setattr(api_routes, "get_lock", lambda _key: RecordingLock())
    monkeypatch.setattr(app.state.fake_redis, "get", guarded_get)
    app.state.dispatch_pipeline.side_effect = guarded_dispatch

    response = await client.post(
        "/api/v1/generate",
        headers=auth_headers(verified_user),
        json={"topic": "Tema valido para lock de refino", "style": "educational", "duration_target": 30},
    )

    assert response.status_code == 202


@pytest.mark.asyncio
async def test_render_initial_redis_failure_refunds_exact_operation_snapshot(
    client,
    db_session,
    verified_user,
    auth_headers,
    job_factory,
    app,
    storage_dir: Path,
    monkeypatch,
):
    job = await job_factory(status="completed", pending_credits=1.5)
    (storage_dir / "jobs" / str(job.id)).mkdir(parents=True)
    original_hset = app.state.fake_redis.hset
    calls = 0

    def fail_initial_hset(key: str, mapping: dict[str, str]):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("redis unavailable")
        return original_hset(key, mapping)

    monkeypatch.setattr(app.state.fake_redis, "hset", fail_initial_hset)

    response = await client.post(f"/api/v1/jobs/{job.id}/render", headers=auth_headers(verified_user))

    assert response.status_code == 503
    db_session.expire_all()
    persisted_job = await db_session.get(Job, job.id)
    persisted_user = await db_session.get(User, verified_user.id)
    assert persisted_user.credits == 5
    assert persisted_job.pending_credits == 1.5
    assert persisted_job.rerender_state == "refunded"
    app.state.rerender_task.delay.assert_not_called()


@pytest.mark.asyncio
async def test_render_marker_failure_after_broker_acceptance_does_not_refund(
    client,
    db_session,
    verified_user,
    auth_headers,
    job_factory,
    app,
    storage_dir: Path,
    monkeypatch,
):
    job = await job_factory(status="completed", pending_credits=1.5)
    (storage_dir / "jobs" / str(job.id)).mkdir(parents=True)

    async def fail_marker(*_args, **_kwargs):
        raise RuntimeError("database unavailable after dispatch")

    monkeypatch.setattr(api_routes, "mark_rerender_dispatched", fail_marker)
    monkeypatch.setattr(api_routes, "_send_admin_alert", lambda *_args, **_kwargs: None)

    response = await client.post(f"/api/v1/jobs/{job.id}/render", headers=auth_headers(verified_user))

    assert response.status_code == 200
    db_session.expire_all()
    persisted_job = await db_session.get(Job, job.id)
    persisted_user = await db_session.get(User, verified_user.id)
    assert persisted_user.credits == 3
    assert persisted_job.pending_credits == 0.0
    assert persisted_job.rerender_state == "debited"
    assert persisted_job.rerender_dispatched_at is None
    app.state.rerender_task.delay.assert_called_once_with(str(job.id), str(persisted_job.rerender_operation_id))


@pytest.mark.asyncio
async def test_render_cancel_flag_delete_failure_is_compensated(
    client,
    db_session,
    verified_user,
    auth_headers,
    job_factory,
    app,
    storage_dir: Path,
    monkeypatch,
):
    job = await job_factory(status="completed", pending_credits=1.5)
    (storage_dir / "jobs" / str(job.id)).mkdir(parents=True)
    cancel_key = f"job:{job.id}:cancelled"
    app.state.fake_redis.set(cancel_key, "true")
    original_delete = app.state.fake_redis.delete

    def fail_cancel_delete(key: str):
        if key == cancel_key:
            raise RuntimeError("redis delete unavailable")
        return original_delete(key)

    monkeypatch.setattr(app.state.fake_redis, "delete", fail_cancel_delete)

    response = await client.post(f"/api/v1/jobs/{job.id}/render", headers=auth_headers(verified_user))

    assert response.status_code == 503
    db_session.expire_all()
    persisted_job = await db_session.get(Job, job.id)
    persisted_user = await db_session.get(User, verified_user.id)
    assert persisted_user.credits == 5
    assert persisted_job.pending_credits == 1.5
    assert persisted_job.rerender_state == "refunded"
    app.state.rerender_task.delay.assert_not_called()


@pytest.mark.asyncio
async def test_undispatched_refunds_revalidate_markers_under_operation_lock(db_session, verified_user, job_factory):
    generation = await job_factory(status="queued")
    persisted_generation = await db_session.get(Job, generation.id)
    persisted_generation.credit_cost = 1
    persisted_user = await db_session.get(User, verified_user.id)
    persisted_user.credits = 4
    await db_session.commit()
    await job_operations.mark_generation_dispatched(db_session, generation.id)
    await db_session.commit()

    rerender = await job_factory(status="completed", pending_credits=1.5)
    operation_id = uuid.uuid4()
    await job_operations.begin_rerender(
        db_session,
        rerender.id,
        verified_user.id,
        operation_id=operation_id,
    )
    await job_operations.mark_rerender_dispatched(db_session, rerender.id, operation_id)
    await db_session.commit()

    assert (
        await job_operations.refund_generation(
            db_session,
            generation.id,
            status="failed",
            error="reconciler race",
            require_undispatched=True,
        )
        is False
    )
    assert (
        await job_operations.refund_rerender(
            db_session,
            rerender.id,
            operation_id,
            require_undispatched=True,
        )
        is False
    )


def test_generation_worker_does_not_run_after_reconciler_refund(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)
    job = create_job(env, status="queued")
    db_engine_module = importlib.import_module("app.db.engine")
    monkeypatch.setattr(db_engine_module, "worker_session", env.session_factory)

    async def refund():
        async with env.session_factory() as session:
            applied = await job_operations.refund_generation(
                session,
                job.id,
                status="failed",
                error="reconciled",
                require_undispatched=True,
            )
            await session.commit()
            return applied

    assert run(refund()) is True
    assert worker_tasks._mark_generation_worker_started(str(job.id)) is False


def test_generation_worker_start_self_heals_dispatch_marker(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)
    job = create_job(env, status="queued")
    db_engine_module = importlib.import_module("app.db.engine")
    monkeypatch.setattr(db_engine_module, "worker_session", env.session_factory)

    assert worker_tasks._mark_generation_worker_started(str(job.id)) is True

    async def read_job():
        async with env.session_factory() as session:
            return await session.get(Job, job.id)

    persisted_job = run(read_job())
    assert persisted_job.generation_dispatched_at is not None


def test_first_generation_worker_self_heals_before_reading_cancel_flag(monkeypatch):
    events: list[str] = []
    monkeypatch.setattr(
        worker_tasks,
        "_mark_generation_worker_started",
        lambda _job_id: events.append("self_heal") or True,
    )
    monkeypatch.setattr(worker_tasks, "_check_cancelled", lambda _job_id: events.append("cancel") or True)

    result = worker_tasks.task_generate_script.run.__func__(
        object(),
        "job-self-heal-order",
        "Tema valido",
        "educational",
        30,
    )

    assert result == {"cancelled": True}
    assert events == ["self_heal", "cancel"]


@pytest.mark.asyncio
async def test_reconciler_refunds_old_undispatched_generation_and_rerender_once(
    db_session,
    test_db,
    verified_user,
    job_factory,
    monkeypatch,
):
    generation = await job_factory(status="queued")
    rerender = await job_factory(status="completed", pending_credits=1.5)
    operation_id = uuid.uuid4()
    old = datetime.now(timezone.utc) - timedelta(hours=7)
    persisted_generation = await db_session.get(Job, generation.id)
    persisted_generation.credit_cost = 1
    persisted_generation.created_at = old
    persisted_user = await db_session.get(User, verified_user.id)
    persisted_user.credits = 4
    await db_session.commit()
    await job_operations.begin_rerender(
        db_session,
        rerender.id,
        verified_user.id,
        operation_id=operation_id,
    )
    persisted_rerender = await db_session.get(Job, rerender.id)
    persisted_rerender.rerender_debited_at = old
    await db_session.commit()
    db_engine_module = importlib.import_module("app.db.engine")
    monkeypatch.setattr(db_engine_module, "worker_session", test_db["session_factory"])

    first = await worker_tasks._reconcile_undispatched_job_operations_async()
    second = await worker_tasks._reconcile_undispatched_job_operations_async()

    db_session.expire_all()
    persisted_generation = await db_session.get(Job, generation.id)
    persisted_rerender = await db_session.get(Job, rerender.id)
    persisted_user = await db_session.get(User, verified_user.id)
    assert first["generation_refunded"] == 1
    assert first["rerender_refunded"] == 1
    assert second["generation_refunded"] == 0
    assert second["rerender_refunded"] == 0
    assert persisted_generation.status == "failed"
    assert persisted_generation.generation_refunded_at is not None
    assert persisted_rerender.rerender_state == "refunded"
    assert persisted_rerender.pending_credits == 1.5
    assert persisted_user.credits == 5


@pytest.mark.asyncio
async def test_reconciler_backfills_dispatch_when_redis_proves_compatible_worker(
    db_session,
    test_db,
    verified_user,
    job_factory,
    app,
    monkeypatch,
):
    generation = await job_factory(status="processing")
    rerender = await job_factory(status="completed", pending_credits=1.5)
    ignored_finalizing = await job_factory(status="finalizing")
    operation_id = uuid.uuid4()
    old = datetime.now(timezone.utc) - timedelta(hours=7)
    persisted_user = await db_session.get(User, verified_user.id)
    persisted_user.credits = 4
    persisted_generation = await db_session.get(Job, generation.id)
    persisted_generation.credit_cost = 1
    persisted_generation.created_at = old
    persisted_ignored = await db_session.get(Job, ignored_finalizing.id)
    persisted_ignored.created_at = old
    await db_session.commit()
    await job_operations.begin_rerender(
        db_session,
        rerender.id,
        verified_user.id,
        operation_id=operation_id,
    )
    persisted_rerender = await db_session.get(Job, rerender.id)
    persisted_rerender.rerender_debited_at = old
    await db_session.commit()
    heartbeat = datetime.now(timezone.utc).isoformat()
    app.state.fake_redis.hset(
        f"job:{generation.id}",
        mapping={"status": "processing", "updated_at": heartbeat},
    )
    app.state.fake_redis.hset(
        f"job:{rerender.id}",
        mapping={
            "status": "rendering",
            "updated_at": heartbeat,
            "rerender_operation_id": str(operation_id),
        },
    )
    db_engine_module = importlib.import_module("app.db.engine")
    monkeypatch.setattr(db_engine_module, "worker_session", test_db["session_factory"])

    result = await worker_tasks._reconcile_undispatched_job_operations_async()

    db_session.expire_all()
    persisted_generation = await db_session.get(Job, generation.id)
    persisted_rerender = await db_session.get(Job, rerender.id)
    persisted_ignored = await db_session.get(Job, ignored_finalizing.id)
    persisted_user = await db_session.get(User, verified_user.id)
    assert result["generation_backfilled"] == 1
    assert result["rerender_backfilled"] == 1
    assert result["generation_refunded"] == 0
    assert result["rerender_refunded"] == 0
    assert persisted_generation.generation_dispatched_at is not None
    assert persisted_rerender.rerender_dispatched_at is not None
    assert persisted_rerender.rerender_state == "dispatched"
    assert persisted_ignored.generation_dispatched_at is None
    assert persisted_ignored.generation_refunded_at is None
    assert persisted_user.credits == 2


@pytest.mark.asyncio
async def test_reconciler_repairs_legacy_cancel_flag_ttls_and_removes_terminal_or_missing(
    test_db,
    job_factory,
    app,
    monkeypatch,
):
    active = await job_factory(status="cancelling")
    delivered = await job_factory(status="editable")
    missing_id = uuid.uuid4()
    active_key = f"job:{active.id}:cancelled"
    delivered_key = f"job:{delivered.id}:cancelled"
    missing_key = f"job:{missing_id}:cancelled"
    for key in (active_key, delivered_key, missing_key):
        app.state.fake_redis.set(key, "true")
    db_engine_module = importlib.import_module("app.db.engine")
    monkeypatch.setattr(db_engine_module, "worker_session", test_db["session_factory"])

    result = await worker_tasks._reconcile_undispatched_job_operations_async()

    assert result["cancel_flags_removed"] == 2
    assert result["cancel_flags_ttl_applied"] == 1
    assert app.state.fake_redis.get(active_key) == "true"
    assert app.state.fake_redis.ttl(active_key) == 24 * 60 * 60
    assert app.state.fake_redis.get(delivered_key) is None
    assert app.state.fake_redis.get(missing_key) is None


def test_celery_beat_schedules_undispatched_reconciler_every_ten_minutes():
    entry = celery_app.conf.beat_schedule["reconcile-undispatched-job-operations"]

    assert entry["task"] == "reconcile_undispatched_job_operations"
    assert entry["schedule"].total_seconds() == 10 * 60
