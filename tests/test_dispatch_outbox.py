import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from celery.exceptions import Ignore
from sqlalchemy import select

from app.db.models import Job, JobDispatch
from app.services import job_operations
from app.services.dispatch_outbox import (
    DispatchPayload,
    claim_generation_dispatch,
    claim_rerender_dispatch,
    create_dispatch,
    publish_dispatch,
)
from app.worker import tasks as worker_tasks


@pytest.mark.asyncio
async def test_pending_generation_dispatch_replays_after_pre_broker_crash(db_session, verified_user):
    """A process death after commit but before broker send leaves replayable work."""
    job = Job(
        user_id=verified_user.id,
        topic="Outbox crash pre-broker",
        style="educational",
        duration_target=30,
        template_id="stock_narration",
        credit_cost=1,
        status="queued",
    )
    db_session.add(job)
    await db_session.flush()
    dispatch = await create_dispatch(
        db_session,
        job_id=job.id,
        operation_id=job.id,
        kind="generation",
        payload=DispatchPayload(
            topic=job.topic,
            style=job.style,
            duration_target=job.duration_target,
            template_id=job.template_id,
        ),
    )
    await db_session.commit()

    # No publisher ran: this is the durable state left by a crash pre-broker.
    sent_task_ids: list[str] = []

    def send(_dispatch: JobDispatch, *, task_id: str) -> None:
        sent_task_ids.append(task_id)

    outcome = await publish_dispatch(db_session, dispatch.id, send=send)

    assert outcome == "published"
    assert len(sent_task_ids) == 1
    uuid.UUID(sent_task_ids[0])
    persisted = await db_session.get(JobDispatch, dispatch.id)
    assert persisted is not None
    assert persisted.published_at is not None
    assert persisted.state == "published"


@pytest.mark.asyncio
async def test_post_accept_marker_failure_replays_with_fresh_id_and_consumer_rejects_duplicate(
    test_db,
    verified_user,
):
    async with test_db["session_factory"]() as setup:
        job = Job(
            user_id=verified_user.id,
            topic="Outbox crash post-accept",
            style="educational",
            duration_target=30,
            template_id="stock_narration",
            credit_cost=1,
            status="queued",
        )
        setup.add(job)
        await setup.flush()
        dispatch = await create_dispatch(
            setup,
            job_id=job.id,
            operation_id=job.id,
            kind="generation",
            payload=DispatchPayload(
                topic=job.topic,
                style=job.style,
                duration_target=job.duration_target,
                template_id=job.template_id,
            ),
        )
        dispatch_id = dispatch.id
        job_id = job.id
        await setup.commit()

    sent_task_ids: list[str] = []

    class ProcessDeath(BaseException):
        pass

    def accepted_then_marker_crashes(_dispatch: JobDispatch, *, task_id: str) -> None:
        sent_task_ids.append(task_id)
        raise ProcessDeath("process died after broker accepted")

    async with test_db["session_factory"]() as first_publish:
        with pytest.raises(ProcessDeath):
            await publish_dispatch(first_publish, dispatch_id, send=accepted_then_marker_crashes)

    async with test_db["session_factory"]() as expire_lease:
        persisted = await expire_lease.get(JobDispatch, dispatch_id)
        assert persisted is not None
        assert persisted.publisher_lease_until is not None
        persisted.publisher_lease_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        await expire_lease.commit()

    def accepted_on_replay(_dispatch: JobDispatch, *, task_id: str) -> None:
        sent_task_ids.append(task_id)

    async with test_db["session_factory"]() as replay:
        assert await publish_dispatch(replay, dispatch_id, send=accepted_on_replay) == "published"

    assert len(sent_task_ids) == 2
    assert sent_task_ids[0] != sent_task_ids[1]

    async def claim_once(task_id: str) -> bool:
        async with test_db["session_factory"]() as session:
            claimed = await claim_generation_dispatch(session, job_id, dispatch_id, task_id=task_id)
            if claimed:
                await session.commit()
            else:
                await session.rollback()
            return claimed

    claims = await asyncio.gather(claim_once(sent_task_ids[0]), claim_once(sent_task_ids[1]))
    assert sorted(claims) == [False, True]

    # Celery retries preserve request.id and must be allowed to resume the same task.
    assert await claim_once(sent_task_ids[claims.index(True)]) is True

    async with test_db["session_factory"]() as verify:
        persisted = await verify.get(JobDispatch, dispatch_id)
        assert persisted is not None
        assert persisted.claimed_at is not None
    assert persisted.state == "claimed"


@pytest.mark.asyncio
async def test_active_publish_lease_prevents_simultaneous_broker_send(db_session, verified_user):
    job = Job(
        user_id=verified_user.id,
        topic="Outbox publisher lease",
        style="educational",
        duration_target=30,
        template_id="stock_narration",
        credit_cost=1,
        status="queued",
    )
    db_session.add(job)
    await db_session.flush()
    dispatch = await create_dispatch(
        db_session,
        job_id=job.id,
        operation_id=job.id,
        kind="generation",
        payload=DispatchPayload(topic=job.topic),
    )
    dispatch.publisher_token = uuid.uuid4()
    dispatch.publisher_lease_until = datetime.now(timezone.utc) + timedelta(minutes=1)
    await db_session.commit()
    sent: list[str] = []

    outcome = await publish_dispatch(
        db_session,
        dispatch.id,
        send=lambda _dispatch, *, task_id: sent.append(task_id),
    )

    assert outcome == "busy"
    assert sent == []


@pytest.mark.asyncio
async def test_stale_pending_dispatch_is_terminally_compensable_not_ambiguous_forever(
    db_session,
    test_db,
    verified_user,
    monkeypatch,
):
    job = Job(
        user_id=verified_user.id,
        topic="Outbox terminal compensation",
        style="educational",
        duration_target=30,
        template_id="stock_narration",
        credit_cost=1,
        status="queued",
    )
    db_session.add(job)
    await db_session.flush()
    dispatch = await create_dispatch(
        db_session,
        job_id=job.id,
        operation_id=job.id,
        kind="generation",
        payload=DispatchPayload(
            topic=job.topic,
            style=job.style,
            duration_target=job.duration_target,
            template_id=job.template_id,
        ),
    )
    dispatch.created_at = datetime.now(timezone.utc) - timedelta(hours=7)
    dispatch.attempt_count = 5
    dispatch.last_error = "broker unavailable"
    dispatch_id = dispatch.id
    job_id = job.id
    persisted_user = await db_session.get(type(verified_user), verified_user.id)
    assert persisted_user is not None
    persisted_user.credits = 4
    await db_session.commit()
    import importlib

    db_engine_module = importlib.import_module("app.db.engine")
    monkeypatch.setattr(db_engine_module, "worker_session", test_db["session_factory"])
    sends = MagicMock(side_effect=RuntimeError("broker unavailable"))
    monkeypatch.setattr(worker_tasks, "_send_job_dispatch_message", sends)

    first = await worker_tasks._reconcile_undispatched_job_operations_async()
    second = await worker_tasks._reconcile_undispatched_job_operations_async()

    db_session.expire_all()
    persisted = await db_session.get(JobDispatch, dispatch_id)
    persisted_job = await db_session.get(Job, job_id)
    persisted_user = await db_session.get(type(verified_user), verified_user.id)
    assert first["dispatch_generation_refunded"] == 1
    assert second["dispatch_generation_refunded"] == 0
    assert persisted is not None and persisted.state == "cancelled"
    assert persisted_job is not None and persisted_job.generation_refunded_at is not None
    assert persisted_user is not None and persisted_user.credits == 5
    assert (
        await claim_generation_dispatch(
            db_session,
            job_id,
            dispatch_id,
            task_id=str(uuid.uuid4()),
        )
        is False
    )
    assert sends.call_count == 0


@pytest.mark.asyncio
async def test_recent_due_pending_dispatch_is_republished_before_terminal_cutoff(
    db_session,
    test_db,
    verified_user,
    monkeypatch,
):
    import importlib

    job = Job(
        user_id=verified_user.id,
        topic="Outbox retry rapido",
        style="educational",
        duration_target=30,
        template_id="stock_narration",
        credit_cost=1,
        status="queued",
    )
    db_session.add(job)
    await db_session.flush()
    dispatch = await create_dispatch(
        db_session,
        job_id=job.id,
        operation_id=job.id,
        kind="generation",
        payload=DispatchPayload(
            topic=job.topic,
            style=job.style,
            duration_target=job.duration_target,
            template_id=job.template_id,
        ),
    )
    dispatch.created_at = datetime.now(timezone.utc) - timedelta(minutes=11)
    dispatch_id = dispatch.id
    job_id = job.id
    await db_session.commit()
    db_engine_module = importlib.import_module("app.db.engine")
    monkeypatch.setattr(db_engine_module, "worker_session", test_db["session_factory"])
    sends = MagicMock()
    monkeypatch.setattr(worker_tasks, "_send_job_dispatch_message", sends)

    result = await worker_tasks._reconcile_undispatched_job_operations_async()

    db_session.expire_all()
    persisted = await db_session.get(JobDispatch, dispatch_id)
    persisted_job = await db_session.get(Job, job_id)
    assert result["dispatch_generation_published"] == 1
    assert persisted is not None and persisted.state == "published"
    assert persisted_job is not None and persisted_job.generation_dispatched_at is not None
    sends.assert_called_once()


@pytest.mark.asyncio
async def test_published_unclaimed_dispatch_is_replayed_then_terminally_refunded(
    db_session,
    test_db,
    verified_user,
    monkeypatch,
):
    import importlib

    old = datetime.now(timezone.utc) - timedelta(hours=7)
    job = Job(
        user_id=verified_user.id,
        topic="Broker aceitou mas consumer nunca iniciou",
        style="educational",
        duration_target=30,
        template_id="stock_narration",
        credit_cost=1,
        status="queued",
        generation_dispatched_at=old,
    )
    db_session.add(job)
    await db_session.flush()
    dispatch = await create_dispatch(
        db_session,
        job_id=job.id,
        operation_id=job.id,
        kind="generation",
        payload=DispatchPayload(
            topic=job.topic,
            style=job.style,
            duration_target=job.duration_target,
            template_id=job.template_id,
        ),
    )
    dispatch.state = "published"
    dispatch.published_at = old
    dispatch.last_attempt_at = old
    dispatch.created_at = old
    dispatch.attempt_count = 4
    dispatch_id = dispatch.id
    job_id = job.id
    persisted_user = await db_session.get(type(verified_user), verified_user.id)
    assert persisted_user is not None
    persisted_user.credits = 4
    await db_session.commit()
    db_engine_module = importlib.import_module("app.db.engine")
    monkeypatch.setattr(db_engine_module, "worker_session", test_db["session_factory"])
    sends = MagicMock()
    monkeypatch.setattr(worker_tasks, "_send_job_dispatch_message", sends)

    first = await worker_tasks._reconcile_undispatched_job_operations_async()
    async with test_db["session_factory"]() as age_retry:
        persisted_dispatch = await age_retry.get(JobDispatch, dispatch_id)
        assert persisted_dispatch is not None
        persisted_dispatch.last_attempt_at = old
        await age_retry.commit()
    second = await worker_tasks._reconcile_undispatched_job_operations_async()
    third = await worker_tasks._reconcile_undispatched_job_operations_async()

    db_session.expire_all()
    persisted = await db_session.get(JobDispatch, dispatch_id)
    persisted_job = await db_session.get(Job, job_id)
    persisted_user = await db_session.get(type(verified_user), verified_user.id)
    assert sends.call_count == 1
    assert first["dispatch_generation_refunded"] == 0
    assert second["dispatch_generation_refunded"] == 1
    assert third["dispatch_generation_refunded"] == 0
    assert persisted is not None and persisted.state == "cancelled"
    assert persisted_job is not None and persisted_job.generation_refunded_at is not None
    assert persisted_user is not None and persisted_user.credits == 5

    assert (
        await claim_generation_dispatch(
            db_session,
            job_id,
            dispatch_id,
            task_id=str(uuid.uuid4()),
        )
        is False
    )


@pytest.mark.asyncio
async def test_published_unclaimed_rerender_replays_then_refunds_exact_snapshot(
    db_session,
    test_db,
    verified_user,
    job_factory,
    monkeypatch,
):
    import importlib

    old = datetime.now(timezone.utc) - timedelta(hours=7)
    persisted_user = await db_session.get(type(verified_user), verified_user.id)
    assert persisted_user is not None
    persisted_user.credits = 5
    await db_session.commit()
    job = await job_factory(status="completed", pending_credits=1.5)
    operation_id = uuid.uuid4()
    operation = await job_operations.begin_rerender(
        db_session,
        job.id,
        verified_user.id,
        operation_id=operation_id,
    )
    dispatch = await create_dispatch(
        db_session,
        job_id=job.id,
        operation_id=operation_id,
        kind="rerender",
        payload=DispatchPayload(rerender_cost=operation.cost),
    )
    job.rerender_state = "dispatched"
    job.rerender_dispatched_at = old
    dispatch.state = "published"
    dispatch.published_at = old
    dispatch.last_attempt_at = old
    dispatch.created_at = old
    dispatch.attempt_count = 4
    dispatch_id = dispatch.id
    job_id = job.id
    await db_session.commit()
    db_engine_module = importlib.import_module("app.db.engine")
    monkeypatch.setattr(db_engine_module, "worker_session", test_db["session_factory"])
    sends = MagicMock()
    monkeypatch.setattr(worker_tasks, "_send_job_dispatch_message", sends)

    first = await worker_tasks._reconcile_undispatched_job_operations_async()
    async with test_db["session_factory"]() as age_retry:
        persisted_dispatch = await age_retry.get(JobDispatch, dispatch_id)
        assert persisted_dispatch is not None
        persisted_dispatch.last_attempt_at = old
        await age_retry.commit()
    second = await worker_tasks._reconcile_undispatched_job_operations_async()
    third = await worker_tasks._reconcile_undispatched_job_operations_async()

    db_session.expire_all()
    persisted = await db_session.get(JobDispatch, dispatch_id)
    persisted_job = await db_session.get(Job, job_id)
    persisted_user = await db_session.get(type(verified_user), verified_user.id)
    assert sends.call_count == 1
    assert first["dispatch_rerender_refunded"] == 0
    assert second["dispatch_rerender_refunded"] == 1
    assert third["dispatch_rerender_refunded"] == 0
    assert persisted is not None and persisted.state == "cancelled"
    assert persisted_job is not None and persisted_job.rerender_state == "refunded"
    assert persisted_job.pending_credits == 1.5
    assert persisted_job.rerender_pending_credits == 1.5
    assert persisted_user is not None and persisted_user.credits == 5
    assert (
        await claim_rerender_dispatch(
            db_session,
            job_id,
            operation_id,
            dispatch_id,
            task_id=str(uuid.uuid4()),
        )
        is False
    )


@pytest.mark.asyncio
async def test_stale_claimed_generation_without_worker_heartbeat_refunds_once(
    db_session,
    test_db,
    verified_user,
    monkeypatch,
):
    import importlib

    old = datetime.now(timezone.utc) - timedelta(minutes=11)
    job = Job(
        user_id=verified_user.id,
        topic="Consumer morreu depois do claim",
        style="educational",
        duration_target=30,
        credit_cost=1,
        status="queued",
        generation_dispatched_at=old,
    )
    db_session.add(job)
    await db_session.flush()
    dispatch = await create_dispatch(
        db_session,
        job_id=job.id,
        operation_id=job.id,
        kind="generation",
        payload=DispatchPayload(topic=job.topic),
    )
    dispatch.state = "claimed"
    dispatch.claimed_at = old
    dispatch.claimed_task_id = uuid.uuid4()
    dispatch.published_at = old
    dispatch_id = dispatch.id
    job_id = job.id
    persisted_user = await db_session.get(type(verified_user), verified_user.id)
    assert persisted_user is not None
    persisted_user.credits = 4
    await db_session.commit()
    db_engine_module = importlib.import_module("app.db.engine")
    monkeypatch.setattr(db_engine_module, "worker_session", test_db["session_factory"])

    first = await worker_tasks._reconcile_undispatched_job_operations_async()
    second = await worker_tasks._reconcile_undispatched_job_operations_async()

    db_session.expire_all()
    persisted = await db_session.get(JobDispatch, dispatch_id)
    persisted_user = await db_session.get(type(verified_user), verified_user.id)
    assert first["dispatch_generation_refunded"] == 1
    assert second["dispatch_generation_refunded"] == 0
    assert persisted is not None and persisted.state == "cancelled"
    assert persisted_user is not None and persisted_user.credits == 5
    assert (
        await claim_generation_dispatch(
            db_session,
            job_id,
            dispatch_id,
            task_id=str(uuid.uuid4()),
        )
        is False
    )


@pytest.mark.asyncio
async def test_stale_claimed_rerender_without_worker_heartbeat_refunds_once(
    db_session,
    test_db,
    verified_user,
    job_factory,
    monkeypatch,
):
    import importlib

    old = datetime.now(timezone.utc) - timedelta(minutes=11)
    persisted_user = await db_session.get(type(verified_user), verified_user.id)
    assert persisted_user is not None
    persisted_user.credits = 5
    await db_session.commit()
    job = await job_factory(status="completed", pending_credits=1.5)
    operation_id = uuid.uuid4()
    await job_operations.begin_rerender(
        db_session,
        job.id,
        verified_user.id,
        operation_id=operation_id,
    )
    dispatch = await create_dispatch(
        db_session,
        job_id=job.id,
        operation_id=operation_id,
        kind="rerender",
        payload=DispatchPayload(rerender_cost=2),
    )
    dispatch.state = "claimed"
    dispatch.claimed_at = old
    dispatch.claimed_task_id = uuid.uuid4()
    dispatch.published_at = old
    persisted_job = await db_session.get(Job, job.id)
    assert persisted_job is not None
    persisted_job.rerender_state = "running"
    persisted_job.rerender_dispatched_at = old
    dispatch_id = dispatch.id
    job_id = job.id
    await db_session.commit()
    db_engine_module = importlib.import_module("app.db.engine")
    monkeypatch.setattr(db_engine_module, "worker_session", test_db["session_factory"])

    first = await worker_tasks._reconcile_undispatched_job_operations_async()
    second = await worker_tasks._reconcile_undispatched_job_operations_async()

    db_session.expire_all()
    persisted = await db_session.get(JobDispatch, dispatch_id)
    persisted_job = await db_session.get(Job, job_id)
    persisted_user = await db_session.get(type(verified_user), verified_user.id)
    assert first["dispatch_rerender_refunded"] == 1
    assert second["dispatch_rerender_refunded"] == 0
    assert persisted is not None and persisted.state == "cancelled"
    assert persisted_job is not None and persisted_job.pending_credits == 1.5
    assert persisted_user is not None and persisted_user.credits == 5
    assert (
        await claim_rerender_dispatch(
            db_session,
            job_id,
            operation_id,
            dispatch_id,
            task_id=str(uuid.uuid4()),
        )
        is False
    )


@pytest.mark.asyncio
async def test_stale_claims_with_post_claim_worker_heartbeats_are_preserved(
    db_session,
    test_db,
    verified_user,
    job_factory,
    app,
    monkeypatch,
):
    import importlib

    old = datetime.now(timezone.utc) - timedelta(minutes=11)
    heartbeat = old + timedelta(seconds=1)
    generation = Job(
        user_id=verified_user.id,
        topic="Consumer vivo",
        style="educational",
        duration_target=30,
        credit_cost=1,
        status="processing",
        generation_dispatched_at=old,
    )
    db_session.add(generation)
    await db_session.flush()
    generation_dispatch = await create_dispatch(
        db_session,
        job_id=generation.id,
        operation_id=generation.id,
        kind="generation",
        payload=DispatchPayload(topic=generation.topic),
    )
    generation_dispatch.state = "claimed"
    generation_dispatch.claimed_at = old
    generation_dispatch.claimed_task_id = uuid.uuid4()
    generation_dispatch.published_at = old
    generation_dispatch_id = generation_dispatch.id
    await db_session.commit()

    rerender = await job_factory(status="completed", pending_credits=1.5)
    operation_id = uuid.uuid4()
    await job_operations.begin_rerender(
        db_session,
        rerender.id,
        verified_user.id,
        operation_id=operation_id,
    )
    rerender_dispatch = await create_dispatch(
        db_session,
        job_id=rerender.id,
        operation_id=operation_id,
        kind="rerender",
        payload=DispatchPayload(rerender_cost=2),
    )
    rerender_dispatch.state = "claimed"
    rerender_dispatch.claimed_at = old
    rerender_dispatch.claimed_task_id = uuid.uuid4()
    rerender_dispatch.published_at = old
    rerender.rerender_state = "running"
    rerender.rerender_dispatched_at = old
    rerender_dispatch_id = rerender_dispatch.id
    await db_session.commit()
    app.state.fake_redis.hset(
        f"job:{generation.id}",
        mapping={"status": "processing", "updated_at": heartbeat.isoformat()},
    )
    app.state.fake_redis.hset(
        f"job:{rerender.id}",
        mapping={
            "status": "rendering",
            "rerender_operation_id": str(operation_id),
            "updated_at": heartbeat.isoformat(),
        },
    )
    db_engine_module = importlib.import_module("app.db.engine")
    monkeypatch.setattr(db_engine_module, "worker_session", test_db["session_factory"])

    result = await worker_tasks._reconcile_undispatched_job_operations_async()

    db_session.expire_all()
    persisted_generation = await db_session.get(JobDispatch, generation_dispatch_id)
    persisted_rerender = await db_session.get(JobDispatch, rerender_dispatch_id)
    assert result["dispatch_generation_refunded"] == 0
    assert result["dispatch_rerender_refunded"] == 0
    assert persisted_generation is not None and persisted_generation.state == "claimed"
    assert persisted_rerender is not None and persisted_rerender.state == "claimed"


@pytest.mark.asyncio
async def test_durable_generation_heartbeat_survives_redis_eviction(
    db_session,
    test_db,
    verified_user,
    app,
    monkeypatch,
):
    import importlib

    old = datetime.now(timezone.utc) - timedelta(minutes=11)
    job = Job(
        user_id=verified_user.id,
        topic="Heartbeat duravel",
        style="educational",
        duration_target=30,
        credit_cost=1,
        status="processing",
        generation_dispatched_at=old,
    )
    db_session.add(job)
    await db_session.flush()
    dispatch = await create_dispatch(
        db_session,
        job_id=job.id,
        operation_id=job.id,
        kind="generation",
        payload=DispatchPayload(topic=job.topic),
    )
    dispatch.state = "claimed"
    dispatch.claimed_at = old
    dispatch.claimed_task_id = uuid.uuid4()
    dispatch.published_at = old
    job_id = job.id
    dispatch_id = dispatch.id
    persisted_user = await db_session.get(type(verified_user), verified_user.id)
    assert persisted_user is not None
    persisted_user.credits = 4
    await db_session.commit()
    db_engine_module = importlib.import_module("app.db.engine")
    monkeypatch.setattr(db_engine_module, "worker_session", test_db["session_factory"])

    await asyncio.to_thread(
        worker_tasks._update_job,
        str(job_id),
        "processing",
        "scripting",
        0.1,
    )
    app.state.fake_redis.delete(f"job:{job_id}")

    result = await worker_tasks._reconcile_undispatched_job_operations_async()

    db_session.expire_all()
    persisted_dispatch = await db_session.get(JobDispatch, dispatch_id)
    persisted_user = await db_session.get(type(verified_user), verified_user.id)
    assert result["dispatch_generation_refunded"] == 0
    assert persisted_dispatch is not None and persisted_dispatch.state == "claimed"
    assert persisted_dispatch.worker_heartbeat_at is not None
    assert persisted_user is not None and persisted_user.credits == 4


@pytest.mark.asyncio
async def test_durable_rerender_heartbeat_survives_redis_eviction(
    db_session,
    test_db,
    verified_user,
    job_factory,
    app,
    monkeypatch,
):
    import importlib

    old = datetime.now(timezone.utc) - timedelta(minutes=11)
    persisted_user = await db_session.get(type(verified_user), verified_user.id)
    assert persisted_user is not None
    persisted_user.credits = 5
    await db_session.commit()
    job = await job_factory(status="completed", pending_credits=1.5)
    operation_id = uuid.uuid4()
    await job_operations.begin_rerender(
        db_session,
        job.id,
        verified_user.id,
        operation_id=operation_id,
    )
    dispatch = await create_dispatch(
        db_session,
        job_id=job.id,
        operation_id=operation_id,
        kind="rerender",
        payload=DispatchPayload(rerender_cost=2),
    )
    dispatch.state = "claimed"
    dispatch.claimed_at = old
    dispatch.claimed_task_id = uuid.uuid4()
    dispatch.published_at = old
    persisted_job = await db_session.get(Job, job.id)
    assert persisted_job is not None
    persisted_job.rerender_state = "running"
    persisted_job.rerender_dispatched_at = old
    job_id = job.id
    dispatch_id = dispatch.id
    await db_session.commit()
    db_engine_module = importlib.import_module("app.db.engine")
    monkeypatch.setattr(db_engine_module, "worker_session", test_db["session_factory"])

    await asyncio.to_thread(
        worker_tasks._update_job,
        str(job_id),
        "rendering",
        "encoding",
        0.3,
    )
    app.state.fake_redis.delete(f"job:{job_id}")

    result = await worker_tasks._reconcile_undispatched_job_operations_async()

    db_session.expire_all()
    persisted_dispatch = await db_session.get(JobDispatch, dispatch_id)
    persisted_job = await db_session.get(Job, job_id)
    persisted_user = await db_session.get(type(verified_user), verified_user.id)
    assert result["dispatch_rerender_refunded"] == 0
    assert persisted_dispatch is not None and persisted_dispatch.state == "claimed"
    assert persisted_dispatch.worker_heartbeat_at is not None
    assert persisted_job is not None and persisted_job.rerender_state == "running"
    assert persisted_user is not None and persisted_user.credits == 3


@pytest.mark.asyncio
async def test_published_unclaimed_under_budget_is_republished_with_fresh_attempt(
    db_session,
    test_db,
    verified_user,
    monkeypatch,
):
    import importlib

    due = datetime.now(timezone.utc) - timedelta(minutes=11)
    job = Job(
        user_id=verified_user.id,
        topic="Published retry budget",
        style="educational",
        duration_target=30,
        status="queued",
        credit_cost=1,
        generation_dispatched_at=due,
    )
    db_session.add(job)
    await db_session.flush()
    dispatch = await create_dispatch(
        db_session,
        job_id=job.id,
        operation_id=job.id,
        kind="generation",
        payload=DispatchPayload(
            topic=job.topic,
            style=job.style,
            duration_target=job.duration_target,
        ),
    )
    dispatch.state = "published"
    dispatch.published_at = due
    dispatch.last_attempt_at = due
    dispatch.created_at = due
    dispatch.attempt_count = 1
    dispatch_id = dispatch.id
    await db_session.commit()
    db_engine_module = importlib.import_module("app.db.engine")
    monkeypatch.setattr(db_engine_module, "worker_session", test_db["session_factory"])
    sends = MagicMock()
    monkeypatch.setattr(worker_tasks, "_send_job_dispatch_message", sends)

    result = await worker_tasks._reconcile_undispatched_job_operations_async()

    db_session.expire_all()
    persisted = await db_session.get(JobDispatch, dispatch_id)
    sends.assert_called_once()
    assert result["dispatch_generation_published"] == 0  # DB marker already existed
    assert persisted is not None and persisted.state == "published"
    assert persisted.attempt_count == 2


@pytest.mark.asyncio
async def test_generate_debit_and_dispatch_outbox_are_persisted_before_publish(
    client,
    auth_headers,
    verified_user,
    test_db,
    app,
):
    response = await client.post(
        "/api/v1/generate",
        headers=auth_headers(verified_user),
        json={
            "topic": "Outbox transacional da geracao",
            "style": "educational",
            "duration_target": 30,
            "sfx_enabled": True,
            "music_enabled": False,
            "custom_script": {
                "narration": "Roteiro congelado para replay.",
                "scenes": [{"text": "Cena congelada", "duration_hint": 5}],
            },
        },
    )

    assert response.status_code == 202
    job_id = uuid.UUID(response.json()["job_id"])
    async with test_db["session_factory"]() as session:
        dispatch = (await session.execute(select(JobDispatch).where(JobDispatch.job_id == job_id))).scalar_one()
        assert dispatch.kind == "generation"
        assert dispatch.operation_id == job_id
        assert dispatch.payload["topic"] == "Outbox transacional da geracao"
        assert dispatch.payload["sfx_enabled"] is True
        assert dispatch.payload["music_enabled"] is False
        assert dispatch.payload["custom_script"] is True
        assert dispatch.state == "published"
        assert dispatch.published_at is not None

    call = app.state.dispatch_pipeline.call_args
    assert call is not None
    assert call.kwargs["dispatch_id"] == str(dispatch.id)
    uuid.UUID(call.kwargs["task_id"])


@pytest.mark.asyncio
async def test_rerender_debit_and_dispatch_outbox_are_persisted_before_publish(
    client,
    auth_headers,
    verified_user,
    test_db,
    job_factory,
    storage_dir,
    monkeypatch,
):
    from app.worker import tasks as worker_tasks

    job = await job_factory(status="completed", pending_credits=1.5)
    (storage_dir / "jobs" / str(job.id)).mkdir(parents=True, exist_ok=True)
    apply_async = MagicMock()
    monkeypatch.setattr(worker_tasks, "task_rerender_video", SimpleNamespace(apply_async=apply_async))

    response = await client.post(
        f"/api/v1/jobs/{job.id}/render",
        headers=auth_headers(verified_user),
    )

    assert response.status_code == 200
    async with test_db["session_factory"]() as session:
        dispatch = (
            await session.execute(
                select(JobDispatch).where(JobDispatch.job_id == job.id, JobDispatch.kind == "rerender")
            )
        ).scalar_one()
        assert dispatch.operation_id is not None
        assert dispatch.state == "published"
        assert dispatch.published_at is not None

    call = apply_async.call_args
    assert call is not None
    assert call.kwargs["args"][:3] == (str(job.id), str(dispatch.operation_id), str(dispatch.id))
    assert call.kwargs["args"][3] == call.kwargs["task_id"]
    uuid.UUID(call.kwargs["task_id"])


def test_duplicate_generation_consumer_is_ignored_before_expensive_work(monkeypatch):
    generated = MagicMock()
    monkeypatch.setattr(worker_tasks, "_mark_generation_worker_started", lambda *_args: False)
    monkeypatch.setattr(worker_tasks, "generate_script", generated)

    with pytest.raises(Ignore):
        worker_tasks.task_generate_script.run.__func__(
            object(),
            "job-duplicate",
            "Tema",
            "educational",
            30,
            "stock_narration",
            None,
            str(uuid.uuid4()),
            str(uuid.uuid4()),
        )

    generated.assert_not_called()


def test_duplicate_rerender_consumer_is_ignored_before_expensive_work(monkeypatch):
    monkeypatch.setattr(worker_tasks, "_claim_rerender_operation", lambda *_args: False)
    get_job_dir = MagicMock()
    monkeypatch.setattr(worker_tasks, "get_job_dir", get_job_dir)

    with pytest.raises(Ignore):
        worker_tasks.task_rerender_video.run.__func__(
            object(),
            "job-duplicate",
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            str(uuid.uuid4()),
        )

    get_job_dir.assert_not_called()


@pytest.mark.asyncio
async def test_generation_refund_cancels_outbox_in_same_transaction(db_session, verified_user):
    job = Job(
        user_id=verified_user.id,
        topic="Refund terminalizes outbox",
        style="educational",
        duration_target=30,
        status="queued",
        credit_cost=1,
    )
    db_session.add(job)
    await db_session.flush()
    dispatch = await create_dispatch(
        db_session,
        job_id=job.id,
        operation_id=job.id,
        kind="generation",
        payload=DispatchPayload(topic=job.topic),
    )
    await db_session.commit()

    assert await job_operations.refund_generation(
        db_session,
        job.id,
        status="failed",
        error="broker indisponivel",
    )
    await db_session.commit()

    await db_session.refresh(dispatch)
    assert dispatch.state == "cancelled"
    assert dispatch.claimed_at is None
    assert (
        await claim_generation_dispatch(
            db_session,
            job.id,
            dispatch.id,
            task_id=str(uuid.uuid4()),
        )
        is False
    )


@pytest.mark.asyncio
async def test_generation_worker_refund_resolves_immutable_outbox_cost_snapshot(db_session, verified_user):
    persisted_user = await db_session.get(type(verified_user), verified_user.id)
    assert persisted_user is not None
    persisted_user.credits = 2
    persisted_user.script_refine_redis_migrated = True
    job = Job(
        user_id=verified_user.id,
        topic="Snapshot financeiro",
        style="educational",
        duration_target=30,
        status="queued",
        credit_cost=3,
        refine_credit_cost=1,
    )
    db_session.add(job)
    await db_session.flush()
    dispatch = await create_dispatch(
        db_session,
        job_id=job.id,
        operation_id=job.id,
        kind="generation",
        payload=DispatchPayload(topic=job.topic),
        debited_credits=3,
        refine_debited=1.0,
    )
    await db_session.commit()

    assert await claim_generation_dispatch(
        db_session,
        job.id,
        dispatch.id,
        task_id=str(uuid.uuid4()),
    )
    await db_session.commit()

    job.credit_cost = 99
    job.refine_credit_cost = 99
    await db_session.commit()
    assert await job_operations.refund_generation(
        db_session,
        job.id,
        status="failed",
        error="refund snapshot",
    )
    await db_session.commit()

    db_session.expire_all()
    persisted_user = await db_session.get(type(verified_user), verified_user.id)
    assert persisted_user is not None
    assert persisted_user.credits == 5
    assert persisted_user.script_refine_pending == 1.0


@pytest.mark.asyncio
async def test_rerender_worker_refund_resolves_immutable_outbox_snapshots(db_session, verified_user, job_factory):
    persisted_user = await db_session.get(type(verified_user), verified_user.id)
    assert persisted_user is not None
    persisted_user.credits = 5
    await db_session.commit()
    job = await job_factory(status="completed", pending_credits=1.5)
    operation_id = uuid.uuid4()
    operation = await job_operations.begin_rerender(
        db_session,
        job.id,
        verified_user.id,
        operation_id=operation_id,
    )
    dispatch = await create_dispatch(
        db_session,
        job_id=job.id,
        operation_id=operation_id,
        kind="rerender",
        payload=DispatchPayload(rerender_cost=operation.cost),
        debited_credits=operation.cost,
        pending_credits_snapshot=operation.pending_credits,
    )
    await db_session.commit()

    assert await claim_rerender_dispatch(
        db_session,
        job.id,
        operation_id,
        dispatch.id,
        task_id=str(uuid.uuid4()),
    )
    await db_session.commit()

    persisted_job = await db_session.get(Job, job.id)
    assert persisted_job is not None
    persisted_job.rerender_cost = 99
    persisted_job.rerender_pending_credits = 99.0
    await db_session.commit()
    assert await job_operations.refund_rerender(
        db_session,
        job.id,
        operation_id,
    )
    await db_session.commit()

    db_session.expire_all()
    persisted_job = await db_session.get(Job, job.id)
    persisted_user = await db_session.get(type(verified_user), verified_user.id)
    assert persisted_job is not None and persisted_job.pending_credits == 1.5
    assert persisted_user is not None and persisted_user.credits == 5


@pytest.mark.asyncio
async def test_generation_completion_terminalizes_outbox(db_session, verified_user):
    job = Job(
        user_id=verified_user.id,
        topic="Completion terminalizes outbox",
        style="educational",
        duration_target=30,
        status="finalizing",
        credit_cost=1,
    )
    db_session.add(job)
    await db_session.flush()
    dispatch = await create_dispatch(
        db_session,
        job_id=job.id,
        operation_id=job.id,
        kind="generation",
        payload=DispatchPayload(topic=job.topic),
    )
    await db_session.commit()

    assert (
        await job_operations.finalize_generation(
            db_session,
            job.id,
            script={"scenes": []},
            video_url="/media/output.mp4",
            telemetry=None,
        )
        == "finalized"
    )
    await db_session.commit()

    await db_session.refresh(dispatch)
    assert dispatch.state == "completed"


@pytest.mark.asyncio
async def test_rerender_refund_terminalizes_exact_outbox(db_session, verified_user, job_factory):
    job = await job_factory(status="completed", pending_credits=1.5)
    operation_id = uuid.uuid4()
    await job_operations.begin_rerender(
        db_session,
        job.id,
        verified_user.id,
        operation_id=operation_id,
    )
    dispatch = await create_dispatch(
        db_session,
        job_id=job.id,
        operation_id=operation_id,
        kind="rerender",
        payload=DispatchPayload(),
    )
    await db_session.commit()

    assert await job_operations.refund_rerender(db_session, job.id, operation_id)
    await db_session.commit()

    await db_session.refresh(dispatch)
    assert dispatch.state == "cancelled"


@pytest.mark.asyncio
async def test_real_locked_rerender_publication_terminalizes_outbox(db_session, verified_user, job_factory):
    job = await job_factory(status="completed")
    operation_id = uuid.uuid4()
    await job_operations.begin_rerender(
        db_session,
        job.id,
        verified_user.id,
        operation_id=operation_id,
    )
    dispatch = await create_dispatch(
        db_session,
        job_id=job.id,
        operation_id=operation_id,
        kind="rerender",
        payload=DispatchPayload(),
    )
    await db_session.commit()
    assert await job_operations.claim_rerender(db_session, job.id, operation_id)
    await db_session.commit()

    locked = await job_operations.lock_rerender_for_publication(db_session, job.id, operation_id)
    assert locked is not None
    assert await job_operations.complete_locked_rerender(db_session, locked, operation_id)
    await db_session.commit()

    await db_session.refresh(dispatch)
    assert dispatch.state == "completed"
