from __future__ import annotations

import math
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Literal

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Job, JobDispatch

DispatchKind = Literal["generation", "rerender"]


@dataclass(frozen=True)
class DispatchPayload:
    topic: str | None = None
    style: str | None = None
    duration_target: int | None = None
    template_id: str | None = None
    voice_provider: str | None = None
    voice_config: dict | None = None
    trend_context: str | None = None
    narration_mode: str | None = None
    sfx_enabled: bool | None = None
    music_enabled: bool | None = None
    custom_script: bool = False
    rerender_cost: int | None = None


async def create_dispatch(
    session: AsyncSession,
    *,
    job_id: uuid.UUID,
    operation_id: uuid.UUID,
    kind: DispatchKind,
    payload: DispatchPayload,
    debited_credits: int | None = None,
    refine_debited: float | None = None,
    pending_credits_snapshot: float | None = None,
) -> JobDispatch:
    # Compatibility fallback for callers/tests created before the financial
    # snapshots existed. Production debit paths pass every value explicitly so
    # the frozen authority is auditable at the debit/outbox transaction.
    if debited_credits is None or refine_debited is None or pending_credits_snapshot is None:
        job = await session.get(Job, job_id)
        if job is None:
            raise ValueError("dispatch job is missing")
        if debited_credits is None:
            debited_credits = int(job.credit_cost if kind == "generation" else job.rerender_cost)
        if refine_debited is None:
            refine_debited = float(job.refine_credit_cost if kind == "generation" else 0.0)
        if pending_credits_snapshot is None:
            pending_credits_snapshot = float(job.rerender_pending_credits if kind == "rerender" else 0.0)
    if (
        debited_credits < 0
        or not math.isfinite(float(refine_debited))
        or refine_debited < 0
        or not math.isfinite(float(pending_credits_snapshot))
        or pending_credits_snapshot < 0
    ):
        raise ValueError("dispatch financial snapshots must be non-negative and finite")
    dispatch = JobDispatch(
        id=uuid.uuid4(),
        job_id=job_id,
        operation_id=operation_id,
        kind=kind,
        payload=asdict(payload),
        debited_credits=debited_credits,
        refine_debited=round(float(refine_debited), 2),
        pending_credits_snapshot=round(float(pending_credits_snapshot), 2),
        state="pending",
    )
    session.add(dispatch)
    await session.flush()
    return dispatch


async def publish_dispatch(
    session: AsyncSession,
    dispatch_id: uuid.UUID,
    *,
    send: Callable[[JobDispatch], None] | Callable[..., None],
    allow_republish: bool = False,
) -> str:
    """Publish a durable outbox row with one broker task id per attempt.

    A crash after ``send`` but before the final marker leaves the row pending.
    Every replay gets a fresh broker task id; the operation outbox accepts the
    first consumer and rejects later task ids, while Celery retries of the winning
    task id remain resumable.
    """
    now = datetime.now(timezone.utc)
    publisher_token = uuid.uuid4()
    broker_task_id = uuid.uuid4()
    lease_until = now + timedelta(minutes=2)
    allowed_states = {"pending", "published"} if allow_republish else {"pending"}
    claim_result = await session.execute(
        update(JobDispatch)
        .where(
            JobDispatch.id == dispatch_id,
            JobDispatch.state.in_(allowed_states),
            JobDispatch.claimed_at.is_(None),
            or_(
                JobDispatch.publisher_lease_until.is_(None),
                JobDispatch.publisher_lease_until <= now,
            ),
        )
        .values(
            state="pending",
            attempt_count=JobDispatch.attempt_count + 1,
            last_attempt_at=now,
            last_task_id=broker_task_id,
            publisher_token=publisher_token,
            publisher_lease_until=lease_until,
            published_at=None,
            last_error=None,
        )
        .returning(JobDispatch)
    )
    dispatch = claim_result.scalar_one_or_none()
    await session.commit()
    if dispatch is None:
        current = await session.get(JobDispatch, dispatch_id)
        if current is None:
            return "missing"
        if current.claimed_at is not None:
            return "claimed"
        if current.published_at is not None and not allow_republish:
            return "published"
        if current.state == "cancelled":
            return "cancelled"
        return "busy"

    try:
        send(dispatch, task_id=str(broker_task_id))
    except Exception as exc:  # noqa: BLE001 - broker outcome can be ambiguous; replay is idempotent
        await session.rollback()
        await session.execute(
            update(JobDispatch)
            .where(
                JobDispatch.id == dispatch_id,
                JobDispatch.published_at.is_(None),
                JobDispatch.claimed_at.is_(None),
                JobDispatch.state != "cancelled",
                JobDispatch.publisher_token == publisher_token,
            )
            .values(
                state="pending",
                last_error=f"send_failed:{exc!r}",
                publisher_token=None,
                publisher_lease_until=None,
            )
        )
        await session.commit()
        return "send_failed"

    accepted_at = datetime.now(timezone.utc)
    await session.execute(
        update(JobDispatch)
        .where(
            JobDispatch.id == dispatch_id,
            JobDispatch.published_at.is_(None),
            JobDispatch.claimed_at.is_(None),
            JobDispatch.state != "cancelled",
            JobDispatch.publisher_token == publisher_token,
        )
        .values(
            state="published",
            published_at=accepted_at,
            last_error=None,
            publisher_token=None,
            publisher_lease_until=None,
        )
    )
    await session.execute(
        update(JobDispatch)
        .where(JobDispatch.id == dispatch_id, JobDispatch.publisher_token == publisher_token)
        .values(publisher_token=None, publisher_lease_until=None)
    )
    await session.commit()
    return "published"


async def claim_generation_dispatch(
    session: AsyncSession,
    job_id: uuid.UUID | str,
    dispatch_id: uuid.UUID,
    *,
    task_id: str,
) -> bool:
    """Claim one generation consumer exactly once, including duplicate broker messages."""
    try:
        parsed_task_id = uuid.UUID(task_id)
    except (TypeError, ValueError):
        return False

    job_result = await session.execute(
        select(Job).where(Job.id == job_id).with_for_update().execution_options(populate_existing=True)
    )
    job = job_result.scalar_one_or_none()
    if (
        job is None
        or job.generation_refunded_at is not None
        or job.status not in {"queued", "processing", "cancelling"}
    ):
        return False
    dispatch_result = await session.execute(
        select(JobDispatch)
        .where(
            JobDispatch.id == dispatch_id,
            JobDispatch.job_id == job.id,
            JobDispatch.operation_id == job.id,
            JobDispatch.kind == "generation",
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    dispatch = dispatch_result.scalar_one_or_none()
    if dispatch is None or dispatch.state == "cancelled" or (dispatch.last_error or "").startswith("send_failed:"):
        return False
    if dispatch.claimed_task_id is not None:
        if dispatch.claimed_task_id != parsed_task_id:
            return False
        if job.generation_dispatched_at is None:
            job.generation_dispatched_at = datetime.now(timezone.utc)
        return True

    now = datetime.now(timezone.utc)
    claim = await session.execute(
        update(JobDispatch)
        .where(
            JobDispatch.id == dispatch_id,
            JobDispatch.job_id == job.id,
            JobDispatch.operation_id == job.id,
            JobDispatch.kind == "generation",
            JobDispatch.claimed_task_id.is_(None),
            JobDispatch.state.in_({"pending", "published"}),
        )
        .values(state="claimed", claimed_at=now, claimed_task_id=parsed_task_id)
    )
    if claim.rowcount != 1:
        return False
    if job.generation_dispatched_at is None:
        job.generation_dispatched_at = now
    return True


async def claim_rerender_dispatch(
    session: AsyncSession,
    job_id: uuid.UUID | str,
    operation_id: uuid.UUID,
    dispatch_id: uuid.UUID,
    *,
    task_id: str,
) -> bool:
    """Claim one exact rerender; a Celery retry may reuse only its own task id."""
    try:
        parsed_task_id = uuid.UUID(task_id)
    except (TypeError, ValueError):
        return False
    job_result = await session.execute(
        select(Job).where(Job.id == job_id).with_for_update().execution_options(populate_existing=True)
    )
    job = job_result.scalar_one_or_none()
    if (
        job is None
        or job.rerender_operation_id != operation_id
        or job.rerender_state not in {"debited", "dispatched", "running"}
    ):
        return False
    dispatch_result = await session.execute(
        select(JobDispatch)
        .where(
            JobDispatch.id == dispatch_id,
            JobDispatch.job_id == job.id,
            JobDispatch.operation_id == operation_id,
            JobDispatch.kind == "rerender",
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    dispatch = dispatch_result.scalar_one_or_none()
    if dispatch is None or dispatch.state == "cancelled" or (dispatch.last_error or "").startswith("send_failed:"):
        return False
    if dispatch.claimed_task_id is not None:
        if dispatch.claimed_task_id != parsed_task_id:
            return False
        if job.rerender_dispatched_at is None:
            job.rerender_dispatched_at = datetime.now(timezone.utc)
        if job.rerender_state in {"debited", "dispatched"}:
            job.rerender_state = "running"
        return True

    now = datetime.now(timezone.utc)
    claim = await session.execute(
        update(JobDispatch)
        .where(
            JobDispatch.id == dispatch_id,
            JobDispatch.claimed_task_id.is_(None),
            JobDispatch.state.in_({"pending", "published"}),
        )
        .values(state="claimed", claimed_at=now, claimed_task_id=parsed_task_id)
    )
    if claim.rowcount != 1:
        return False
    if job.rerender_dispatched_at is None:
        job.rerender_dispatched_at = now
    job.rerender_state = "running"
    return True
