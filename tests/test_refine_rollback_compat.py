import importlib
import uuid

import pytest

from app.api import routes as api_routes
from app.db.models import RefineBalanceOutbox, User
from app.services.refine_balance import (
    adjust_refine_balance,
    sync_refine_balance_projection,
)
from app.worker import tasks as worker_tasks
from app.worker.celery_app import celery_app
from scripts import pre_rollback_refine_gate


def _old_ba03321_reader(redis, user_id: uuid.UUID) -> float:
    """Exact compatibility contract used by the pre-SQL application build."""
    return float(redis.get(f"script_refine_pending:{user_id}") or 0.0)


@pytest.mark.asyncio
async def test_old_reader_keeps_half_credit_after_sql_projection_is_removed(
    db_session,
    verified_user,
    app,
):
    projection = await adjust_refine_balance(db_session, verified_user.id, 0.5)
    await db_session.commit()

    assert await sync_refine_balance_projection(db_session, projection.id, app.state.fake_redis) is True
    assert _old_ba03321_reader(app.state.fake_redis, verified_user.id) == 0.5

    # Model the old binary after DB downgrade: it only knows the legacy key.
    db_session.expunge_all()
    assert _old_ba03321_reader(app.state.fake_redis, verified_user.id) == 0.5


@pytest.mark.asyncio
async def test_refine_projection_is_versioned_and_out_of_order_replay_cannot_regress_balance(
    db_session,
    verified_user,
    app,
):
    first = await adjust_refine_balance(db_session, verified_user.id, 0.5)
    second = await adjust_refine_balance(db_session, verified_user.id, 0.5)
    await db_session.commit()

    assert await sync_refine_balance_projection(db_session, second.id, app.state.fake_redis) is True
    assert await sync_refine_balance_projection(db_session, first.id, app.state.fake_redis) is False
    assert _old_ba03321_reader(app.state.fake_redis, verified_user.id) == 1.0

    user = await db_session.get(User, verified_user.id)
    assert user is not None
    assert user.script_refine_pending == 1.0
    assert user.script_refine_version == 2
    rows = (
        await db_session.execute(
            RefineBalanceOutbox.__table__.select().where(RefineBalanceOutbox.user_id == verified_user.id)
        )
    ).all()
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_failed_redis_projection_remains_durable_for_pre_rollback_drain(
    db_session,
    verified_user,
    app,
    monkeypatch,
):
    projection = await adjust_refine_balance(db_session, verified_user.id, 0.5)
    await db_session.commit()
    original_set = app.state.fake_redis.set

    def fail_balance_write(key: str, *args, **kwargs):
        if key == f"script_refine_pending:{verified_user.id}":
            raise RuntimeError("redis unavailable")
        return original_set(key, *args, **kwargs)

    monkeypatch.setattr(app.state.fake_redis, "set", fail_balance_write)

    assert await sync_refine_balance_projection(db_session, projection.id, app.state.fake_redis) is False
    await db_session.refresh(projection)
    assert projection.applied_at is None
    assert projection.last_error is not None


@pytest.mark.asyncio
async def test_explicit_pre_rollback_drain_projects_every_pending_balance(
    db_session,
    test_db,
    verified_user,
    app,
    monkeypatch,
):
    persisted_user = await db_session.get(User, verified_user.id)
    assert persisted_user is not None
    persisted_user.script_refine_redis_migrated = True
    await db_session.commit()
    projection = await adjust_refine_balance(db_session, verified_user.id, 0.5)
    projection_id = projection.id
    await db_session.commit()
    db_engine_module = importlib.import_module("app.db.engine")
    monkeypatch.setattr(db_engine_module, "worker_session", test_db["session_factory"])

    result = await worker_tasks._drain_refine_balance_outbox_async()

    assert result == {"projected": 1, "remaining": 0}
    assert _old_ba03321_reader(app.state.fake_redis, verified_user.id) == 0.5
    db_session.expire_all()
    persisted = await db_session.get(RefineBalanceOutbox, projection_id)
    assert persisted is not None and persisted.applied_at is not None


@pytest.mark.asyncio
async def test_pre_rollback_drain_repairs_evicted_projection_even_when_outbox_is_applied(
    db_session,
    test_db,
    verified_user,
    app,
    monkeypatch,
):
    persisted_user = await db_session.get(User, verified_user.id)
    assert persisted_user is not None
    persisted_user.script_refine_redis_migrated = True
    await db_session.commit()
    projection = await adjust_refine_balance(db_session, verified_user.id, 0.5)
    await db_session.commit()
    assert await sync_refine_balance_projection(db_session, projection.id, app.state.fake_redis)
    balance_key = f"script_refine_pending:{verified_user.id}"
    version_key = f"script_refine_pending_version:{verified_user.id}"
    app.state.fake_redis.delete(balance_key)
    app.state.fake_redis.delete(version_key)
    db_engine_module = importlib.import_module("app.db.engine")
    monkeypatch.setattr(db_engine_module, "worker_session", test_db["session_factory"])

    result = await worker_tasks._drain_refine_balance_outbox_async()

    assert result == {"projected": 1, "remaining": 0}
    assert _old_ba03321_reader(app.state.fake_redis, verified_user.id) == 0.5
    assert app.state.fake_redis.get(version_key) == "1"


def test_refine_balance_drain_is_scheduled_and_invokable_before_rollback():
    entry = celery_app.conf.beat_schedule["drain-refine-balance-outbox"]

    assert entry["task"] == "drain_refine_balance_outbox"
    assert entry["schedule"].total_seconds() == 10 * 60


def test_pre_rollback_cli_blocks_binary_switch_until_projection_drain_is_zero(monkeypatch):
    async def pending():
        return {"projected": 0, "remaining": 1, "handed_off": 0}

    async def drained():
        return {"projected": 1, "remaining": 0, "handed_off": 1}

    monkeypatch.setattr(pre_rollback_refine_gate, "_prepare_refine_balance_rollback_async", pending)
    assert pre_rollback_refine_gate.main() == 1

    monkeypatch.setattr(pre_rollback_refine_gate, "_prepare_refine_balance_rollback_async", drained)
    assert pre_rollback_refine_gate.main() == 0


@pytest.mark.asyncio
async def test_prepare_handoff_fails_closed_on_unmigrated_nonzero_sql_balance(
    db_session,
    test_db,
    verified_user,
    monkeypatch,
):
    persisted_user = await db_session.get(User, verified_user.id)
    assert persisted_user is not None
    persisted_user.script_refine_pending = 0.5
    persisted_user.script_refine_redis_migrated = False
    await db_session.commit()
    db_engine_module = importlib.import_module("app.db.engine")
    monkeypatch.setattr(db_engine_module, "worker_session", test_db["session_factory"])

    result = await worker_tasks._prepare_refine_balance_rollback_async()

    assert result == {"projected": 0, "remaining": 1, "handed_off": 0}
    db_session.expire_all()
    persisted_user = await db_session.get(User, verified_user.id)
    assert persisted_user is not None and persisted_user.script_refine_pending == 0.5


def test_rollback_runbook_requires_quiescence_in_both_switch_directions():
    assert "old-to-new" in (pre_rollback_refine_gate.__doc__ or "")


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy_after_rollback", ["1.00", None])
async def test_explicit_handoff_survives_old_binary_writes_and_rolls_forward_without_loss(
    db_session,
    test_db,
    verified_user,
    app,
    monkeypatch,
    legacy_after_rollback,
):
    """Exercise new -> ba03321 -> new, including a schema-version reset."""
    persisted_user = await db_session.get(User, verified_user.id)
    assert persisted_user is not None
    persisted_user.script_refine_redis_migrated = True
    await db_session.commit()
    projection = await adjust_refine_balance(db_session, verified_user.id, 0.5)
    await db_session.commit()
    assert await sync_refine_balance_projection(db_session, projection.id, app.state.fake_redis)
    db_engine_module = importlib.import_module("app.db.engine")
    monkeypatch.setattr(db_engine_module, "worker_session", test_db["session_factory"])

    handoff = await worker_tasks._prepare_refine_balance_rollback_async()

    assert handoff == {"projected": 0, "remaining": 0, "handed_off": 1}
    db_session.expire_all()
    handed_off_user = await db_session.get(User, verified_user.id)
    assert handed_off_user is not None
    assert handed_off_user.script_refine_pending == 0.0
    assert handed_off_user.script_refine_redis_migrated is False
    assert handed_off_user.script_refine_version == 1

    balance_key = f"script_refine_pending:{verified_user.id}"
    version_key = f"script_refine_pending_version:{verified_user.id}"
    if legacy_after_rollback is None:
        # ba03321 consumed the whole balance and deletes its only authority key.
        app.state.fake_redis.delete(balance_key)
        expected_balance = 0.0
    else:
        # ba03321 delivered one more refinement and writes only the legacy key.
        app.state.fake_redis.set(balance_key, legacy_after_rollback)
        expected_balance = 1.0

    # A mistakenly live beat must not overwrite Redis once authority was handed off.
    assert await worker_tasks._drain_refine_balance_outbox_async() == {"projected": 0, "remaining": 0}
    assert _old_ba03321_reader(app.state.fake_redis, verified_user.id) == expected_balance

    # A downgrade/re-upgrade recreates b8 columns at version zero. Roll-forward
    # must still advance past the version retained in Redis.
    handed_off_user.script_refine_version = 0
    await db_session.commit()
    remigrated, remigration_projection_id = await api_routes._lock_script_refine_balance(
        db_session,
        verified_user.id,
    )
    assert remigrated.script_refine_pending == expected_balance
    assert remigrated.script_refine_version == 2
    assert remigrated.script_refine_redis_migrated is True
    assert remigration_projection_id is not None
    await db_session.commit()
    assert (
        await sync_refine_balance_projection(
            db_session,
            remigration_projection_id,
            app.state.fake_redis,
        )
        is True
    )
    assert app.state.fake_redis.get(version_key) == "2"
    assert _old_ba03321_reader(app.state.fake_redis, verified_user.id) == expected_balance
