from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from math import ceil

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Job, User


class InvalidJobOperation(ValueError):
    """The persisted job state does not allow the requested transition."""


class InsufficientCredits(InvalidJobOperation):
    """The user cannot fund the requested operation."""


@dataclass(frozen=True)
class RerenderOperation:
    operation_id: uuid.UUID
    cost: int
    pending_credits: float


async def request_generation_cancel(session: AsyncSession, job_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    """Persist a generation cancellation request under a row lock.

    Returns ``True`` for the first transition and ``False`` for an idempotent
    repeat. Transaction ownership remains with the caller.
    """
    result = await session.execute(
        select(Job)
        .where(Job.id == job_id, Job.user_id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise InvalidJobOperation("Job not found")
    if job.video_url is not None or job.completed_at is not None or job.status in {"editable", "completed"}:
        raise InvalidJobOperation("Only an active, undelivered generation can be cancelled")
    if job.status == "cancelling":
        return False
    if job.status not in {"queued", "processing"}:
        raise InvalidJobOperation("Only an active, undelivered generation can be cancelled")

    job.status = "cancelling"
    job.cancel_requested_at = datetime.now(timezone.utc)
    return True


async def mark_generation_dispatched(session: AsyncSession, job_id: uuid.UUID | str) -> bool:
    """Persist the successful handoff to the generation queue once."""
    result = await session.execute(
        select(Job).where(Job.id == job_id).with_for_update().execution_options(populate_existing=True)
    )
    job = result.scalar_one_or_none()
    if (
        job is None
        or job.generation_dispatched_at is not None
        or job.generation_refunded_at is not None
        or job.status not in {"queued", "processing", "cancelling"}
    ):
        return False
    job.generation_dispatched_at = datetime.now(timezone.utc)
    return True


async def claim_generation_worker_start(session: AsyncSession, job_id: uuid.UUID | str) -> bool:
    """Atomically allow accepted generation work unless reconciliation already refunded it."""
    result = await session.execute(
        select(Job).where(Job.id == job_id).with_for_update().execution_options(populate_existing=True)
    )
    job = result.scalar_one_or_none()
    if (
        job is None
        or job.generation_refunded_at is not None
        or job.status not in {"queued", "processing", "cancelling"}
    ):
        return False
    if job.generation_dispatched_at is None:
        job.generation_dispatched_at = datetime.now(timezone.utc)
    return True


async def refund_generation(
    session: AsyncSession,
    job_id: uuid.UUID | str,
    *,
    status: str,
    error: str,
    require_undispatched: bool = False,
) -> bool:
    """Refund an undelivered generation exactly once under a row lock."""
    result = await session.execute(
        select(Job).where(Job.id == job_id).with_for_update().execution_options(populate_existing=True)
    )
    job = result.scalar_one_or_none()
    if (
        job is None
        or job.generation_refunded_at is not None
        or (require_undispatched and job.generation_dispatched_at is not None)
        or job.status not in {"queued", "processing", "cancelling", "finalizing"}
        or job.video_url is not None
        or job.completed_at is not None
    ):
        return False

    refund_amount = job.credit_cost or 1
    await session.execute(
        update(User)
        .where(User.id == job.user_id)
        .values(
            credits=User.credits + refund_amount,
            script_refine_pending=User.script_refine_pending + (job.refine_credit_cost or 0),
        )
    )
    job.status = status
    job.error = error
    job.generation_refunded_at = datetime.now(timezone.utc)
    return True


async def claim_generation_finalize(session: AsyncSession, job_id: uuid.UUID | str) -> str:
    """Claim final publication before any canonical generation artifact is produced."""
    result = await session.execute(
        select(Job).where(Job.id == job_id).with_for_update().execution_options(populate_existing=True)
    )
    job = result.scalar_one_or_none()
    if job is None:
        return "missing"
    if job.video_url is not None or job.completed_at is not None or job.status in {"editable", "completed"}:
        return "delivered"
    if job.status == "cancelling" or job.cancel_requested_at is not None or job.generation_refunded_at is not None:
        return "cancelled"
    if job.status == "finalizing":
        return "in_progress"
    if job.status not in {"queued", "processing"}:
        return "ignored"
    job.status = "finalizing"
    return "claimed"


async def finalize_generation(
    session: AsyncSession,
    job_id: uuid.UUID | str,
    *,
    script: dict | None,
    video_url: str,
    telemetry: dict | None,
) -> str:
    """Atomically publish delivery only while generation still owns the DB transition."""
    result = await session.execute(
        select(Job).where(Job.id == job_id).with_for_update().execution_options(populate_existing=True)
    )
    job = result.scalar_one_or_none()
    if job is None:
        return "missing"
    if (
        job.status == "finalizing"
        and job.cancel_requested_at is None
        and job.generation_refunded_at is None
        and job.video_url is None
        and job.completed_at is None
    ):
        job.script = script
        job.status = "editable"
        job.video_url = video_url
        job.telemetry = telemetry
        job.completed_at = datetime.now(timezone.utc)
        return "finalized"
    if (
        (job.status == "cancelling" or job.cancel_requested_at is not None)
        and job.video_url is None
        and job.completed_at is None
    ):
        return "cancelled"
    return "ignored"


async def begin_rerender(
    session: AsyncSession,
    job_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    operation_id: uuid.UUID,
) -> RerenderOperation:
    """Snapshot, debit, and persist one rerender operation atomically."""
    result = await session.execute(
        select(Job)
        .where(Job.id == job_id, Job.user_id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    job = result.scalar_one_or_none()
    if job is None or job.status not in {"editable", "completed"}:
        raise InvalidJobOperation("Only a delivered job can be rendered")
    if job.rerender_state in {"debited", "dispatched", "running"}:
        raise InvalidJobOperation("A rerender is already active")

    snapshot = float(job.pending_credits or 0.0)
    cost = ceil(snapshot)
    if cost > 0:
        debit = await session.execute(
            update(User)
            .where(User.id == user_id, User.email_verified.is_(True), User.credits >= cost)
            .values(credits=User.credits - cost)
        )
        if debit.rowcount == 0:
            raise InsufficientCredits("Insufficient credits")

    now = datetime.now(timezone.utc)
    job.rerender_operation_id = operation_id
    job.rerender_state = "debited"
    job.rerender_cost = cost
    job.rerender_pending_credits = snapshot
    job.rerender_debited_at = now
    job.rerender_dispatched_at = None
    job.pending_credits = 0.0
    return RerenderOperation(operation_id=operation_id, cost=cost, pending_credits=snapshot)


async def mark_rerender_dispatched(session: AsyncSession, job_id: uuid.UUID | str, operation_id: uuid.UUID) -> bool:
    result = await session.execute(
        select(Job).where(Job.id == job_id).with_for_update().execution_options(populate_existing=True)
    )
    job = result.scalar_one_or_none()
    if job is None or job.rerender_operation_id != operation_id or job.rerender_state not in {"debited", "running"}:
        return False
    if job.rerender_state == "debited":
        job.rerender_state = "dispatched"
    if job.rerender_dispatched_at is None:
        job.rerender_dispatched_at = datetime.now(timezone.utc)
    return True


async def claim_rerender(session: AsyncSession, job_id: uuid.UUID | str, operation_id: uuid.UUID) -> bool:
    """CAS an exact queued operation to running."""
    result = await session.execute(
        select(Job).where(Job.id == job_id).with_for_update().execution_options(populate_existing=True)
    )
    job = result.scalar_one_or_none()
    if job is None or job.rerender_operation_id != operation_id or job.rerender_state not in {"debited", "dispatched"}:
        return False
    if job.rerender_dispatched_at is None:
        job.rerender_dispatched_at = datetime.now(timezone.utc)
    job.rerender_state = "running"
    return True


async def complete_rerender(session: AsyncSession, job_id: uuid.UUID | str, operation_id: uuid.UUID) -> bool:
    """CAS an exact running operation to completed."""
    result = await session.execute(
        select(Job).where(Job.id == job_id).with_for_update().execution_options(populate_existing=True)
    )
    job = result.scalar_one_or_none()
    if job is None or job.rerender_operation_id != operation_id or job.rerender_state != "running":
        return False
    job.rerender_state = "completed"
    return True


async def refund_rerender(
    session: AsyncSession,
    job_id: uuid.UUID | str,
    operation_id: uuid.UUID,
    *,
    require_undispatched: bool = False,
) -> bool:
    """Refund one exact active rerender and restore its fractional snapshot."""
    result = await session.execute(
        select(Job).where(Job.id == job_id).with_for_update().execution_options(populate_existing=True)
    )
    job = result.scalar_one_or_none()
    if (
        job is None
        or job.rerender_operation_id != operation_id
        or job.rerender_state not in {"debited", "dispatched", "running"}
        or (require_undispatched and (job.rerender_state != "debited" or job.rerender_dispatched_at is not None))
    ):
        return False

    if job.rerender_cost > 0:
        await session.execute(
            update(User).where(User.id == job.user_id).values(credits=User.credits + job.rerender_cost)
        )
    await session.execute(
        update(Job)
        .where(Job.id == job.id)
        .values(pending_credits=func.coalesce(Job.pending_credits, 0.0) + job.rerender_pending_credits)
    )
    job.rerender_state = "refunded"
    return True


async def lock_rerender_for_publication(
    session: AsyncSession,
    job_id: uuid.UUID | str,
    operation_id: uuid.UUID | None,
) -> Job | None:
    """Hold the job row while an exact operation publishes its canonical artifact."""
    result = await session.execute(
        select(Job).where(Job.id == job_id).with_for_update().execution_options(populate_existing=True)
    )
    job = result.scalar_one_or_none()
    if job is None or job.rerender_state != "running":
        return None
    if operation_id is None:
        return job if job.rerender_operation_id is None else None
    return job if job.rerender_operation_id == operation_id else None


def complete_locked_rerender(job: Job, operation_id: uuid.UUID | None) -> bool:
    """Complete the exact operation while its publication row lock is still held."""
    if job.rerender_state != "running":
        return False
    if operation_id is None:
        if job.rerender_operation_id is not None:
            return False
    elif job.rerender_operation_id != operation_id:
        return False
    job.rerender_state = "completed"
    return True


async def claim_legacy_rerender(session: AsyncSession, job_id: uuid.UUID | str) -> bool:
    """Claim a pre-deploy task only when no durable operation can be confused with it."""
    result = await session.execute(
        select(Job).where(Job.id == job_id).with_for_update().execution_options(populate_existing=True)
    )
    job = result.scalar_one_or_none()
    if job is None or job.rerender_operation_id is not None or job.rerender_state != "idle":
        return False
    job.rerender_state = "running"
    return True


async def finish_legacy_rerender(
    session: AsyncSession,
    job_id: uuid.UUID | str,
    *,
    state: str,
) -> bool:
    """Close a claimed legacy task without inferring a modern operation UUID."""
    if state not in {"completed", "refunded"}:
        raise ValueError("Invalid legacy rerender terminal state")
    result = await session.execute(
        select(Job).where(Job.id == job_id).with_for_update().execution_options(populate_existing=True)
    )
    job = result.scalar_one_or_none()
    if job is None or job.rerender_operation_id is not None or job.rerender_state != "running":
        return False
    job.rerender_state = state
    return True
