from __future__ import annotations

import asyncio
import importlib
import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import routes as api_routes
from app.db.models import Job, User
from app.services import job_operations
from app.worker import tasks as worker_tasks
from tests.voice_test_support import create_job, create_test_env, run


def test_job_operation_model_and_migration_metadata_are_coherent():
    columns = Job.__table__.c
    expected = {
        "generation_dispatched_at",
        "generation_refunded_at",
        "cancel_requested_at",
        "rerender_operation_id",
        "rerender_state",
        "rerender_cost",
        "rerender_pending_credits",
        "rerender_debited_at",
        "rerender_dispatched_at",
    }

    assert expected <= set(columns.keys())
    assert columns.rerender_state.default.arg == "idle"
    assert str(columns.rerender_state.server_default.arg) == "idle"
    assert columns.rerender_cost.default.arg == 0
    assert str(columns.rerender_cost.server_default.arg) == "0"
    assert columns.rerender_pending_credits.default.arg == 0.0
    assert str(columns.rerender_pending_credits.server_default.arg) in {"0", "0.0"}
    assert any(
        [column.name for column in index.columns] == ["rerender_state", "rerender_debited_at"]
        for index in Job.__table__.indexes
    )

    versions_dir = Path(__file__).parents[1] / "alembic" / "versions"
    migrations = [
        path for path in versions_dir.glob("*.py") if "generation_dispatched_at" in path.read_text(encoding="utf-8")
    ]
    assert len(migrations) == 1
    migration = migrations[0].read_text(encoding="utf-8")
    assert 'down_revision: str | None = "d4e5f6a7b8c9"' in migration
    assert "generation_dispatched_at = created_at" in migration
    assert "generation_refunded_at = created_at" not in migration


@pytest.mark.asyncio
async def test_cancel_delivered_job_returns_409_without_setting_redis_flag(
    client, verified_user, auth_headers, job_factory, app
):
    job = await job_factory(status="editable")

    response = await client.post(f"/api/v1/jobs/{job.id}/cancel", headers=auth_headers(verified_user))

    assert response.status_code == 409
    assert app.state.fake_redis.get(f"job:{job.id}:cancelled") is None


@pytest.mark.asyncio
async def test_cancel_cancelling_job_with_delivery_evidence_returns_409_without_flag(
    client, db_session, verified_user, auth_headers, job_factory, app
):
    job = await job_factory(status="cancelling")
    persisted_job = await db_session.get(Job, job.id)
    persisted_job.video_url = "/storage/output/already-delivered.mp4"
    await db_session.commit()

    response = await client.post(f"/api/v1/jobs/{job.id}/cancel", headers=auth_headers(verified_user))

    assert response.status_code == 409
    assert app.state.fake_redis.get(f"job:{job.id}:cancelled") is None


@pytest.mark.asyncio
async def test_active_cancel_persists_before_redis_and_is_idempotent_with_24h_ttl(
    client,
    db_session,
    verified_user,
    auth_headers,
    job_factory,
    app,
    monkeypatch,
):
    job = await job_factory(status="processing")
    events: list[str] = []
    redis_sets: list[tuple[str, str, int | None]] = []
    original_commit = AsyncSession.commit
    original_set = app.state.fake_redis.set

    async def recording_commit(self):
        await original_commit(self)
        events.append("db_commit")

    def recording_set(key: str, value: str, ex: int | None = None, nx: bool = False):
        events.append("redis_set")
        redis_sets.append((key, value, ex))
        return original_set(key, value, ex=ex, nx=nx)

    monkeypatch.setattr(AsyncSession, "commit", recording_commit)
    monkeypatch.setattr(app.state.fake_redis, "set", recording_set)

    first = await client.post(f"/api/v1/jobs/{job.id}/cancel", headers=auth_headers(verified_user))
    db_session.expire_all()
    after_first = await db_session.get(Job, job.id)

    assert first.status_code == 200
    assert after_first.status == "cancelling"
    assert after_first.cancel_requested_at is not None
    first_cancel_requested_at = after_first.cancel_requested_at
    assert events.index("db_commit") < events.index("redis_set")
    assert redis_sets[-1] == (f"job:{job.id}:cancelled", "true", 24 * 60 * 60)

    second = await client.post(f"/api/v1/jobs/{job.id}/cancel", headers=auth_headers(verified_user))
    db_session.expire_all()
    after_second = await db_session.get(Job, job.id)

    assert second.status_code == 200
    assert second.json() == {"status": "cancelling"}
    assert after_second.status == "cancelling"
    assert after_second.cancel_requested_at == first_cancel_requested_at


@pytest.mark.asyncio
async def test_generation_refund_is_one_shot_and_uses_relative_balance_update(db_session, verified_user, job_factory):
    assert hasattr(job_operations, "refund_generation")
    job = await job_factory(status="processing")
    persisted_job = await db_session.get(Job, job.id)
    persisted_job.credit_cost = 3
    await db_session.commit()

    first = await job_operations.refund_generation(
        db_session,
        job.id,
        status="cancelled",
        error="cancelled by user",
    )
    await db_session.commit()
    first_refunded_at = persisted_job.generation_refunded_at

    second = await job_operations.refund_generation(
        db_session,
        job.id,
        status="cancelled",
        error="duplicate",
    )
    await db_session.commit()
    persisted_user = await db_session.get(User, verified_user.id)
    await db_session.refresh(persisted_user)
    await db_session.refresh(persisted_job)

    assert first is True
    assert second is False
    assert persisted_user.credits == 8
    assert persisted_job.status == "cancelled"
    assert persisted_job.error == "cancelled by user"
    assert persisted_job.generation_refunded_at.replace(tzinfo=None) == first_refunded_at.replace(tzinfo=None)


@pytest.mark.asyncio
async def test_generation_refund_is_noop_after_delivery(db_session, verified_user, job_factory):
    assert hasattr(job_operations, "refund_generation")
    job = await job_factory(status="editable")
    persisted_job = await db_session.get(Job, job.id)
    persisted_job.video_url = "/storage/output/delivered.mp4"
    await db_session.commit()

    refunded = await job_operations.refund_generation(
        db_session,
        job.id,
        status="failed",
        error="late worker failure",
    )
    await db_session.commit()
    persisted_user = await db_session.get(User, verified_user.id)
    await db_session.refresh(persisted_user)
    await db_session.refresh(persisted_job)

    assert refunded is False
    assert persisted_user.credits == 5
    assert persisted_job.status == "editable"
    assert persisted_job.video_url == "/storage/output/delivered.mp4"
    assert persisted_job.generation_refunded_at is None


def test_worker_generation_refund_never_overwrites_delivered_job(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)
    job = create_job(env, status="editable", credit_cost=3)

    async def mark_delivered():
        async with env.session_factory() as session:
            persisted_job = await session.get(Job, job.id)
            persisted_job.video_url = "/storage/output/delivered.mp4"
            await session.commit()

    run(mark_delivered())
    db_engine_module = importlib.import_module("app.db.engine")
    monkeypatch.setattr(db_engine_module, "worker_session", env.session_factory)
    env.fake_redis.hset(f"job:{job.id}", mapping={"status": "completed"})

    applied = worker_tasks._refund_job_credit(str(job.id), "failed", "late worker failure")

    async def read_state():
        async with env.session_factory() as session:
            persisted_job = await session.get(Job, job.id)
            persisted_user = await session.get(User, env.verified_user.id)
            return persisted_job, persisted_user

    persisted_job, persisted_user = run(read_state())
    assert applied is False
    assert persisted_job.status == "editable"
    assert persisted_job.video_url == "/storage/output/delivered.mp4"
    assert persisted_job.generation_refunded_at is None
    assert persisted_user.credits == 10
    assert env.fake_redis.hgetall(f"job:{job.id}")["status"] == "completed"


@pytest.mark.asyncio
async def test_rerender_operation_snapshots_debits_and_rejects_second_active_attempt(
    db_session, verified_user, job_factory
):
    assert hasattr(job_operations, "begin_rerender")
    job = await job_factory(status="completed", pending_credits=1.5)
    operation_id = uuid.uuid4()

    operation = await job_operations.begin_rerender(
        db_session,
        job.id,
        verified_user.id,
        operation_id=operation_id,
    )
    await db_session.commit()
    persisted_job = await db_session.get(Job, job.id)
    persisted_user = await db_session.get(User, verified_user.id)
    await db_session.refresh(persisted_job)
    await db_session.refresh(persisted_user)

    assert operation.operation_id == operation_id
    assert operation.cost == 2
    assert operation.pending_credits == 1.5
    assert persisted_job.rerender_operation_id == operation_id
    assert persisted_job.rerender_state == "debited"
    assert persisted_job.rerender_cost == 2
    assert persisted_job.rerender_pending_credits == 1.5
    assert persisted_job.rerender_debited_at is not None
    assert persisted_job.pending_credits == 0.0
    assert persisted_user.credits == 3

    with pytest.raises(job_operations.InvalidJobOperation):
        await job_operations.begin_rerender(
            db_session,
            job.id,
            verified_user.id,
            operation_id=uuid.uuid4(),
        )
    await db_session.rollback()
    await db_session.refresh(persisted_user)
    assert persisted_user.credits == 3


@pytest.mark.asyncio
async def test_rerender_refund_is_one_shot_restores_fraction_and_stale_operation_cannot_mutate(
    db_session, verified_user, job_factory
):
    required = {"begin_rerender", "claim_rerender", "complete_rerender", "refund_rerender"}
    assert required <= set(dir(job_operations))
    job = await job_factory(status="completed", pending_credits=1.5)
    first_id = uuid.uuid4()
    stale_id = uuid.uuid4()
    await job_operations.begin_rerender(
        db_session,
        job.id,
        verified_user.id,
        operation_id=first_id,
    )
    await db_session.commit()

    assert await job_operations.claim_rerender(db_session, job.id, stale_id) is False
    assert await job_operations.refund_rerender(db_session, job.id, stale_id) is False
    assert await job_operations.complete_rerender(db_session, job.id, stale_id) is False
    assert await job_operations.claim_rerender(db_session, job.id, first_id) is True
    await db_session.commit()
    assert await job_operations.claim_rerender(db_session, job.id, first_id) is False

    assert await job_operations.refund_rerender(db_session, job.id, first_id) is True
    await db_session.commit()
    assert await job_operations.refund_rerender(db_session, job.id, first_id) is False
    persisted_job = await db_session.get(Job, job.id)
    persisted_user = await db_session.get(User, verified_user.id)
    await db_session.refresh(persisted_job)
    await db_session.refresh(persisted_user)
    assert persisted_job.rerender_state == "refunded"
    assert persisted_job.pending_credits == 1.5
    assert persisted_user.credits == 5

    second_id = uuid.uuid4()
    await job_operations.begin_rerender(
        db_session,
        job.id,
        verified_user.id,
        operation_id=second_id,
    )
    await db_session.commit()
    assert await job_operations.claim_rerender(db_session, job.id, second_id) is True
    assert await job_operations.refund_rerender(db_session, job.id, first_id) is False
    assert await job_operations.complete_rerender(db_session, job.id, first_id) is False
    assert await job_operations.complete_rerender(db_session, job.id, second_id) is True
    await db_session.commit()
    await db_session.refresh(persisted_job)
    await db_session.refresh(persisted_user)
    assert persisted_job.rerender_operation_id == second_id
    assert persisted_job.rerender_state == "completed"
    assert persisted_job.pending_credits == 0.0
    assert persisted_user.credits == 3


@pytest.mark.asyncio
async def test_worker_claim_before_route_dispatch_still_persists_dispatched_timestamp(
    db_session, verified_user, job_factory
):
    job = await job_factory(status="completed")
    operation_id = uuid.uuid4()
    await job_operations.begin_rerender(
        db_session,
        job.id,
        verified_user.id,
        operation_id=operation_id,
    )
    await db_session.commit()

    assert await job_operations.claim_rerender(db_session, job.id, operation_id) is True
    await db_session.commit()
    assert await job_operations.mark_rerender_dispatched(db_session, job.id, operation_id) is True
    await db_session.commit()

    persisted_job = await db_session.get(Job, job.id)
    await db_session.refresh(persisted_job)
    assert persisted_job.rerender_state == "running"
    assert persisted_job.rerender_dispatched_at is not None


@pytest.mark.asyncio
async def test_legacy_rerender_claim_only_runs_without_a_new_operation(db_session, job_factory):
    required = {"claim_legacy_rerender", "finish_legacy_rerender"}
    assert required <= set(dir(job_operations))
    job = await job_factory(status="completed")

    assert await job_operations.claim_legacy_rerender(db_session, job.id) is True
    await db_session.commit()
    assert await job_operations.claim_legacy_rerender(db_session, job.id) is False
    assert await job_operations.finish_legacy_rerender(db_session, job.id, state="completed") is True
    await db_session.commit()

    persisted_job = await db_session.get(Job, job.id)
    persisted_job.rerender_operation_id = uuid.uuid4()
    persisted_job.rerender_state = "dispatched"
    await db_session.commit()
    assert await job_operations.claim_legacy_rerender(db_session, job.id) is False


@pytest.mark.asyncio
async def test_render_route_persists_operation_clears_legacy_cancel_and_rejects_second_active(
    client,
    db_session,
    verified_user,
    auth_headers,
    job_factory,
    app,
    storage_dir,
):
    job = await job_factory(status="completed", pending_credits=1.5)
    (storage_dir / "jobs" / str(job.id)).mkdir(parents=True)
    app.state.fake_redis.set(f"job:{job.id}:cancelled", "true")

    first = await client.post(f"/api/v1/jobs/{job.id}/render", headers=auth_headers(verified_user))
    second = await client.post(f"/api/v1/jobs/{job.id}/render", headers=auth_headers(verified_user))
    db_session.expire_all()
    persisted_job = await db_session.get(Job, job.id)
    persisted_user = await db_session.get(User, verified_user.id)

    assert first.status_code == 200
    assert second.status_code == 409
    assert persisted_job.rerender_operation_id is not None
    assert persisted_job.rerender_state in {"dispatched", "running"}
    assert persisted_job.rerender_cost == 2
    assert persisted_job.rerender_pending_credits == 1.5
    assert persisted_job.pending_credits == 0.0
    assert persisted_user.credits == 3
    assert app.state.fake_redis.get(f"job:{job.id}:cancelled") is None
    live = app.state.fake_redis.hgetall(f"job:{job.id}")
    assert live["rerender_operation_id"] == str(persisted_job.rerender_operation_id)
    app.state.rerender_task.delay.assert_called_once_with(
        str(job.id),
        str(persisted_job.rerender_operation_id),
    )


def test_render_and_cancel_openapi_document_invalid_state_conflicts(app):
    schema = app.openapi()
    assert "409" in schema["paths"]["/api/v1/jobs/{job_id}/render"]["post"]["responses"]
    assert "409" in schema["paths"]["/api/v1/jobs/{job_id}/cancel"]["post"]["responses"]


@pytest.mark.asyncio
async def test_invalid_render_does_not_clear_active_generation_cancel_flag(
    client,
    verified_user,
    auth_headers,
    job_factory,
    app,
    storage_dir,
):
    job = await job_factory(status="queued")
    (storage_dir / "jobs" / str(job.id)).mkdir(parents=True)
    app.state.fake_redis.set(f"job:{job.id}:cancelled", "true")

    response = await client.post(f"/api/v1/jobs/{job.id}/render", headers=auth_headers(verified_user))

    assert response.status_code == 409
    assert app.state.fake_redis.get(f"job:{job.id}:cancelled") == "true"
    app.state.rerender_task.delay.assert_not_called()


@pytest.mark.asyncio
async def test_ai_suggest_during_rerender_and_refund_preserve_both_credit_buckets(
    client,
    db_session,
    verified_user,
    auth_headers,
    job_factory,
    storage_dir,
    monkeypatch,
):
    job = await job_factory(
        status="completed",
        pending_credits=1.5,
        script={"scenes": [{"text": "original", "duration_hint": 7}]},
    )
    (storage_dir / "jobs" / str(job.id)).mkdir(parents=True)
    llm_started = threading.Event()
    release_llm = threading.Event()

    def delayed_suggestion(*_args, **_kwargs):
        llm_started.set()
        assert release_llm.wait(timeout=5)
        return '{"suggestions": [], "general_feedback": "ok"}'

    monkeypatch.setattr("app.api.routes.complete_text", delayed_suggestion)
    suggestion_task = asyncio.create_task(
        client.post(
            f"/api/v1/jobs/{job.id}/ai-suggest",
            headers=auth_headers(verified_user),
            json={"message": "melhore", "context": {"scenes": []}},
        )
    )
    assert await asyncio.to_thread(llm_started.wait, 5)

    render_response = await client.post(f"/api/v1/jobs/{job.id}/render", headers=auth_headers(verified_user))
    release_llm.set()
    suggestion_response = await suggestion_task

    assert render_response.status_code == 200
    assert suggestion_response.status_code == 200
    db_session.expire_all()
    persisted_job = await db_session.get(Job, job.id)
    assert persisted_job.pending_credits == 0.5

    assert (
        await job_operations.refund_rerender(
            db_session,
            job.id,
            persisted_job.rerender_operation_id,
        )
        is True
    )
    await db_session.commit()
    await db_session.refresh(persisted_job)
    assert persisted_job.pending_credits == 2.0


def test_rerender_worker_stale_operation_exits_before_redis_or_filesystem(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)
    job = create_job(env, status="completed", pending_credits=1.5)
    current_id = uuid.uuid4()

    async def begin():
        async with env.session_factory() as session:
            await job_operations.begin_rerender(
                session,
                job.id,
                env.verified_user.id,
                operation_id=current_id,
            )
            await session.commit()

    run(begin())
    db_engine_module = importlib.import_module("app.db.engine")
    monkeypatch.setattr(db_engine_module, "worker_session", env.session_factory)
    updates: list[tuple] = []
    monkeypatch.setattr(worker_tasks, "_update_job", lambda *args, **kwargs: updates.append((args, kwargs)))
    monkeypatch.setattr(
        worker_tasks,
        "get_job_dir",
        lambda _job_id: (_ for _ in ()).throw(AssertionError("stale task touched filesystem")),
    )
    monkeypatch.setattr(
        worker_tasks,
        "_check_cancelled",
        lambda _job_id: (_ for _ in ()).throw(AssertionError("rerender read generation cancel flag")),
    )

    result = worker_tasks.task_rerender_video.run.__func__(
        object(),
        str(job.id),
        str(uuid.uuid4()),
    )

    assert result == ""
    assert updates == []


def test_rerender_claim_infrastructure_failure_propagates_for_retry(monkeypatch):
    async def database_unavailable(*_args, **_kwargs):
        raise RuntimeError("database unavailable during claim")

    monkeypatch.setattr(job_operations, "claim_rerender", database_unavailable)

    with pytest.raises(RuntimeError, match="database unavailable during claim"):
        worker_tasks._claim_rerender_operation("job-claim-db-down", str(uuid.uuid4()))


@pytest.mark.parametrize("terminal_status", ["completed", "error"])
def test_old_rerender_terminal_cannot_overwrite_new_operation_redis(monkeypatch, terminal_status):
    assert hasattr(worker_tasks, "_update_rerender_terminal")
    old_operation_id = uuid.uuid4()
    new_operation_id = uuid.uuid4()
    job_id = "job-terminal-race"
    redis_key = f"job:{job_id}"
    worker_tasks._redis.hset(
        redis_key,
        mapping={
            "rerender_operation_id": str(new_operation_id),
            "status": "rendering",
            "detail": "new operation",
        },
    )

    updated = worker_tasks._update_rerender_terminal(
        job_id,
        str(old_operation_id),
        status=terminal_status,
        error="old operation error" if terminal_status == "error" else "",
        detail="old operation terminal",
    )

    assert updated is False
    assert worker_tasks._redis.hgetall(redis_key) == {
        "rerender_operation_id": str(new_operation_id),
        "status": "rendering",
        "detail": "new operation",
    }


def test_rerender_worker_ignores_generation_cancel_and_completes_matching_operation(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)
    job = create_job(env, status="completed", pending_credits=1.5)
    operation_id = uuid.uuid4()
    job_dir = env.storage_dir / "jobs" / str(job.id)
    (job_dir / "media").mkdir(parents=True)
    (job_dir / "script.json").write_text(json.dumps({"scenes": [{"duration_hint": 1}]}), encoding="utf-8")
    (job_dir / "words.json").write_text("[]", encoding="utf-8")
    (job_dir / "narration.wav").write_bytes(b"audio")
    (job_dir / "media" / "background.mp4").write_bytes(b"video")
    output_dir = env.storage_dir / "output"
    output_dir.mkdir()

    async def begin():
        async with env.session_factory() as session:
            await job_operations.begin_rerender(
                session,
                job.id,
                env.verified_user.id,
                operation_id=operation_id,
            )
            await job_operations.mark_rerender_dispatched(session, job.id, operation_id)
            await session.commit()

    run(begin())
    db_engine_module = importlib.import_module("app.db.engine")
    monkeypatch.setattr(db_engine_module, "worker_session", env.session_factory)
    monkeypatch.setattr(worker_tasks.settings, "RENDER_ENGINE", "remotion")
    monkeypatch.setattr(worker_tasks, "append_outro", lambda path: path)
    monkeypatch.setattr(worker_tasks, "_write_thumbnail", lambda *_args: None)
    monkeypatch.setattr(worker_tasks, "get_output_dir", lambda: output_dir)
    remotion = importlib.import_module("app.services.remotion")

    def fake_render(_job_id, output_path, **_kwargs):
        Path(output_path).write_bytes(b"rendered")

    monkeypatch.setattr(remotion, "invoke_remotion_render", fake_render)
    env.fake_redis.set(f"job:{job.id}:cancelled", "true")

    final_path = worker_tasks.task_rerender_video.run.__func__(
        object(),
        str(job.id),
        str(operation_id),
    )

    async def read_state():
        async with env.session_factory() as session:
            persisted_job = await session.get(Job, job.id)
            persisted_user = await session.get(User, env.verified_user.id)
            return persisted_job, persisted_user

    persisted_job, persisted_user = run(read_state())
    assert Path(final_path).read_bytes() == b"rendered"
    assert persisted_job.rerender_state == "completed"
    assert persisted_job.generation_refunded_at is None
    assert persisted_user.credits == 8
    assert not (job_dir / f"final_remotion_{operation_id}.mp4").exists()


def test_rerender_stale_after_claim_cannot_publish_output_or_telemetry(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)
    job = create_job(env, status="completed", pending_credits=1.5)
    old_operation_id = uuid.uuid4()
    new_operation_id = uuid.uuid4()
    job_dir = env.storage_dir / "jobs" / str(job.id)
    (job_dir / "media").mkdir(parents=True)
    (job_dir / "script.json").write_text(json.dumps({"scenes": [{"duration_hint": 1}]}), encoding="utf-8")
    (job_dir / "words.json").write_text("[]", encoding="utf-8")
    (job_dir / "narration.wav").write_bytes(b"audio")
    (job_dir / "media" / "background.mp4").write_bytes(b"video")
    output_dir = env.storage_dir / "output"
    output_dir.mkdir()
    canonical_output = output_dir / f"{job.id}.mp4"
    canonical_output.write_bytes(b"new-operation-output")
    preserved_telemetry = {"rerenders": [{"engine": "new-operation", "duration_seconds": 1}]}

    async def begin_old_operation():
        async with env.session_factory() as session:
            await job_operations.begin_rerender(
                session,
                job.id,
                env.verified_user.id,
                operation_id=old_operation_id,
            )
            await job_operations.mark_rerender_dispatched(session, job.id, old_operation_id)
            await session.commit()

    run(begin_old_operation())
    db_engine_module = importlib.import_module("app.db.engine")
    monkeypatch.setattr(db_engine_module, "worker_session", env.session_factory)
    monkeypatch.setattr(worker_tasks.settings, "RENDER_ENGINE", "remotion")
    monkeypatch.setattr(worker_tasks, "append_outro", lambda path: path)
    monkeypatch.setattr(worker_tasks, "_write_thumbnail", lambda *_args: None)
    monkeypatch.setattr(worker_tasks, "get_output_dir", lambda: output_dir)
    remotion = importlib.import_module("app.services.remotion")

    def render_then_make_operation_stale(_job_id, output_path, **_kwargs):
        Path(output_path).write_bytes(b"stale-operation-output")

        async def replace_operation():
            async with env.session_factory() as session:
                persisted_job = await session.get(Job, job.id)
                persisted_job.rerender_operation_id = new_operation_id
                persisted_job.rerender_state = "running"
                persisted_job.telemetry = preserved_telemetry
                await session.commit()

        run(replace_operation())

    monkeypatch.setattr(remotion, "invoke_remotion_render", render_then_make_operation_stale)

    result = worker_tasks.task_rerender_video.run.__func__(
        object(),
        str(job.id),
        str(old_operation_id),
    )

    async def read_state():
        async with env.session_factory() as session:
            return await session.get(Job, job.id)

    persisted_job = run(read_state())
    assert result == ""
    assert canonical_output.read_bytes() == b"new-operation-output"
    assert persisted_job.rerender_operation_id == new_operation_id
    assert persisted_job.rerender_state == "running"
    assert persisted_job.telemetry == preserved_telemetry
    assert env.fake_redis.hgetall(f"job:{job.id}").get("status") != "completed"
    assert not (job_dir / f"final_remotion_{old_operation_id}.mp4").exists()


def test_rerender_prepares_video_and_thumbnail_before_publication_row_lock(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)
    job = create_job(env, status="completed")
    operation_id = uuid.uuid4()
    operation_output = tmp_path / "operation.mp4"
    operation_output.write_bytes(b"rendered")
    output_dir = env.storage_dir / "output"
    output_dir.mkdir()

    async def begin_and_claim():
        async with env.session_factory() as session:
            await job_operations.begin_rerender(
                session,
                job.id,
                env.verified_user.id,
                operation_id=operation_id,
            )
            await job_operations.claim_rerender(session, job.id, operation_id)
            await session.commit()

    run(begin_and_claim())
    db_engine_module = importlib.import_module("app.db.engine")
    monkeypatch.setattr(db_engine_module, "worker_session", env.session_factory)
    monkeypatch.setattr(worker_tasks, "get_output_dir", lambda: output_dir)
    events: list[str] = []
    original_lock = job_operations.lock_rerender_for_publication

    async def recording_lock(*args, **kwargs):
        events.append("lock")
        return await original_lock(*args, **kwargs)

    def recording_outro(path):
        events.append("append_outro")
        return path

    def recording_thumbnail(_video_path, thumb_path):
        events.append("thumbnail")
        Path(thumb_path).write_bytes(b"thumb")

    monkeypatch.setattr(job_operations, "lock_rerender_for_publication", recording_lock)
    monkeypatch.setattr(worker_tasks, "append_outro", recording_outro)
    monkeypatch.setattr(worker_tasks, "_write_thumbnail", recording_thumbnail)

    published = worker_tasks._publish_rerender_operation(
        str(job.id),
        str(operation_id),
        str(operation_output),
        engine="remotion",
        duration=1.0,
    )

    assert published is not None
    assert events.index("append_outro") < events.index("lock")
    assert events.index("thumbnail") < events.index("lock")


def _prepare_finalize_env(tmp_path, monkeypatch, *, status: str):
    env = create_test_env(tmp_path, monkeypatch)
    job = create_job(env, status=status, credit_cost=3)
    job_dir = env.storage_dir / "jobs" / str(job.id)
    job_dir.mkdir(parents=True)
    (job_dir / "script.json").write_text(json.dumps({"scenes": []}), encoding="utf-8")
    source = tmp_path / "composed.mp4"
    source.write_bytes(b"video")
    output_dir = env.storage_dir / "output"
    output_dir.mkdir()
    db_engine_module = importlib.import_module("app.db.engine")
    monkeypatch.setattr(db_engine_module, "worker_session", env.session_factory)
    monkeypatch.setattr(worker_tasks, "get_job_dir", lambda _job_id: job_dir)
    monkeypatch.setattr(worker_tasks, "get_output_dir", lambda: output_dir)
    monkeypatch.setattr(worker_tasks, "append_outro", lambda path: path)
    monkeypatch.setattr(worker_tasks, "_write_thumbnail", lambda *_args: None)
    monkeypatch.setattr(worker_tasks, "_build_telemetry", lambda *_args: {})
    return env, job, source, output_dir


def test_finalize_that_loses_db_race_to_cancel_never_delivers(tmp_path, monkeypatch):
    env, job, source, output_dir = _prepare_finalize_env(tmp_path, monkeypatch, status="cancelling")

    async def mark_cancel_requested():
        async with env.session_factory() as session:
            persisted_job = await session.get(Job, job.id)
            persisted_job.cancel_requested_at = datetime.now(timezone.utc)
            await session.commit()

    run(mark_cancel_requested())

    result = worker_tasks.task_finalize.run.__func__(object(), str(source), str(job.id))

    async def read_state():
        async with env.session_factory() as session:
            persisted_job = await session.get(Job, job.id)
            persisted_user = await session.get(User, env.verified_user.id)
            return persisted_job, persisted_user

    persisted_job, persisted_user = run(read_state())
    assert result == ""
    assert persisted_job.status == "cancelled"
    assert persisted_job.video_url is None
    assert persisted_job.completed_at is None
    assert persisted_job.generation_refunded_at is not None
    assert persisted_user.credits == 13
    assert not (output_dir / f"{job.id}.mp4").exists()
    assert env.fake_redis.hgetall(f"job:{job.id}").get("status") != "completed"


@pytest.mark.asyncio
async def test_finalize_claim_blocks_late_cancel(db_session, verified_user, job_factory):
    assert hasattr(job_operations, "claim_generation_finalize")
    job = await job_factory(status="processing")
    claimed = await job_operations.claim_generation_finalize(db_session, job.id)
    await db_session.commit()
    with pytest.raises(job_operations.InvalidJobOperation):
        await job_operations.request_generation_cancel(db_session, job.id, verified_user.id)

    assert claimed == "claimed"
    persisted_job = await db_session.get(Job, job.id)
    await db_session.refresh(persisted_job)
    assert persisted_job.status == "finalizing"


def test_finalize_ignored_job_removes_stale_downloadable_artifacts(tmp_path, monkeypatch):
    env, job, source, output_dir = _prepare_finalize_env(tmp_path, monkeypatch, status="failed")
    canonical_video = output_dir / f"{job.id}.mp4"
    canonical_thumbnail = output_dir / f"{job.id}.jpg"
    canonical_video.write_bytes(b"stale-video")
    canonical_thumbnail.write_bytes(b"stale-thumbnail")

    result = worker_tasks.task_finalize.run.__func__(object(), str(source), str(job.id))

    async def try_download():
        async with env.session_factory() as session:
            return await api_routes.download_job(str(job.id), user=env.verified_user, db=session)

    assert result == ""
    assert not canonical_video.exists()
    assert not canonical_thumbnail.exists()
    with pytest.raises(HTTPException) as exc_info:
        run(try_download())
    assert exc_info.value.status_code == 404


def test_generation_finalize_prepares_artifacts_before_final_publication_lock(tmp_path, monkeypatch):
    env, job, source, output_dir = _prepare_finalize_env(tmp_path, monkeypatch, status="processing")
    events: list[str] = []
    original_finalize = job_operations.finalize_generation

    def recording_outro(path):
        events.append("append_outro")
        return path

    def recording_thumbnail(_video_path, thumb_path):
        events.append("thumbnail")
        Path(thumb_path).write_bytes(b"thumb")

    async def recording_finalize(*args, **kwargs):
        events.append("lock")
        assert list(output_dir.glob(f".{job.id}.*.prepared.mp4"))
        assert list(output_dir.glob(f".{job.id}.*.prepared.jpg"))
        assert not (output_dir / f"{job.id}.mp4").exists()
        return await original_finalize(*args, **kwargs)

    monkeypatch.setattr(worker_tasks, "append_outro", recording_outro)
    monkeypatch.setattr(worker_tasks, "_write_thumbnail", recording_thumbnail)
    monkeypatch.setattr(job_operations, "finalize_generation", recording_finalize)

    published = worker_tasks.task_finalize.run.__func__(object(), str(source), str(job.id))

    assert published.endswith(f"{job.id}.mp4")
    assert events.index("append_outro") < events.index("lock")
    assert events.index("thumbnail") < events.index("lock")


def test_finalize_success_commits_delivery_then_clears_cancel_flag(tmp_path, monkeypatch):
    env, job, source, _output_dir = _prepare_finalize_env(tmp_path, monkeypatch, status="processing")
    deleted: list[str] = []

    def delete(key: str):
        deleted.append(key)
        env.fake_redis.values.pop(key, None)

    monkeypatch.setattr(env.fake_redis, "delete", delete, raising=False)

    result = worker_tasks.task_finalize.run.__func__(object(), str(source), str(job.id))

    async def read_state():
        async with env.session_factory() as session:
            return await session.get(Job, job.id)

    persisted_job = run(read_state())
    assert result.endswith(f"{job.id}.mp4")
    assert persisted_job.status == "editable"
    assert persisted_job.video_url == result
    assert persisted_job.completed_at is not None
    assert deleted == [f"job:{job.id}:cancelled"]
    assert env.fake_redis.hgetall(f"job:{job.id}")["status"] == "completed"


def test_finalize_db_failure_never_publishes_completed(tmp_path, monkeypatch):
    env, job, source, output_dir = _prepare_finalize_env(tmp_path, monkeypatch, status="processing")

    async def db_failure(*_args, **_kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(job_operations, "finalize_generation", db_failure)

    with pytest.raises(RuntimeError, match="database unavailable"):
        worker_tasks.task_finalize.run.__func__(object(), str(source), str(job.id))

    assert env.fake_redis.hgetall(f"job:{job.id}").get("status") != "completed"
    assert not (output_dir / f"{job.id}.mp4").exists()


@pytest.mark.asyncio
async def test_generate_records_generation_dispatched_after_successful_dispatch(
    client,
    db_session,
    verified_user,
    auth_headers,
):
    response = await client.post(
        "/api/v1/generate",
        headers=auth_headers(verified_user),
        json={"topic": "Tema valido para dispatch persistente", "style": "educational", "duration_target": 30},
    )

    assert response.status_code == 202
    job = await db_session.get(Job, uuid.UUID(response.json()["job_id"]))
    assert job.generation_dispatched_at is not None
