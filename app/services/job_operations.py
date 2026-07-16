from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from math import ceil

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.service import append_server_event_safely
from app.db.models import Job, JobDispatch, User
from app.services.acquisition_rewards import claim_referral_activation_reward
from app.services.credit_ledger import set_credit_ledger_context
from app.services.refine_balance import adjust_refine_balance


class InvalidJobOperation(ValueError):
    """The persisted job state does not allow the requested transition."""


class InsufficientCredits(InvalidJobOperation):
    """The user cannot fund the requested operation."""


@dataclass(frozen=True)
class RerenderOperation:
    operation_id: uuid.UUID
    cost: int
    pending_credits: float


async def _analytics_user(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.get(User, user_id)


async def _generation_ordinal(session: AsyncSession, job: Job) -> str:
    conditions = [Job.user_id == job.user_id]
    if job.created_at is not None:
        conditions.append(Job.created_at <= job.created_at)
    count = int(await session.scalar(select(func.count(Job.id)).where(*conditions)) or 0)
    return "first" if count <= 1 else "second" if count == 2 else "repeat"


async def _lock_operation_dispatch(
    session: AsyncSession,
    *,
    job_id: uuid.UUID,
    operation_id: uuid.UUID,
    kind: str,
    dispatch_id: uuid.UUID | None,
) -> JobDispatch | None:
    """Resolve the immutable financial authority after the Job row is locked."""
    statement = select(JobDispatch).where(
        JobDispatch.job_id == job_id,
        JobDispatch.operation_id == operation_id,
        JobDispatch.kind == kind,
    )
    if dispatch_id is not None:
        statement = statement.where(JobDispatch.id == dispatch_id)
    result = await session.execute(statement.with_for_update().execution_options(populate_existing=True))
    return result.scalar_one_or_none()


def _dispatch_allows_refund(
    dispatch: JobDispatch | None,
    *,
    explicit_dispatch: bool,
    require_undispatched: bool,
    allow_claimed: bool,
) -> bool:
    if dispatch is None:
        return not explicit_dispatch
    if dispatch.state not in {"pending", "published", "claimed"}:
        return False
    if require_undispatched:
        return dispatch.claimed_at is None and dispatch.state in {"pending", "published"}
    if dispatch.claimed_at is not None or dispatch.state == "claimed":
        # A normal worker refund resolves its already-claimed operation without
        # receiving an outbox id. Explicit compensation remains fail-closed
        # unless reconciliation deliberately opts into a stale claimed row.
        return allow_claimed or not explicit_dispatch
    return True


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
    outbox_dispatch_id: uuid.UUID | None = None,
    allow_claimed_outbox: bool = False,
) -> bool:
    """Refund an undelivered generation exactly once under a row lock."""
    result = await session.execute(
        select(Job).where(Job.id == job_id).with_for_update().execution_options(populate_existing=True)
    )
    job = result.scalar_one_or_none()
    dispatch = (
        await _lock_operation_dispatch(
            session,
            job_id=job.id,
            operation_id=job.id,
            kind="generation",
            dispatch_id=outbox_dispatch_id,
        )
        if job is not None
        else None
    )
    dispatch_allowed = _dispatch_allows_refund(
        dispatch,
        explicit_dispatch=outbox_dispatch_id is not None,
        require_undispatched=require_undispatched,
        allow_claimed=allow_claimed_outbox,
    )
    if (
        job is None
        or job.generation_refunded_at is not None
        or not dispatch_allowed
        or (require_undispatched and dispatch is None and job.generation_dispatched_at is not None)
        or job.status not in {"queued", "processing", "cancelling", "finalizing"}
        or job.video_url is not None
        or job.completed_at is not None
    ):
        return False

    refund_amount = dispatch.debited_credits if dispatch is not None else (job.credit_cost or 1)
    refine_refund = dispatch.refine_debited if dispatch is not None else float(job.refine_credit_cost or 0)
    if refund_amount < 0 or refine_refund < 0:
        return False
    if refund_amount > 0:
        await set_credit_ledger_context(
            session,
            origin="generation_refund",
            reason="undelivered generation refunded",
            idempotency_key=f"generation:{job.id}:refund",
            job_id=job.id,
            operation_id=job.id,
        )
        await session.execute(update(User).where(User.id == job.user_id).values(credits=User.credits + refund_amount))
    if refine_refund:
        await adjust_refine_balance(session, job.user_id, float(refine_refund))
    job.status = status
    job.error = error
    job.generation_refunded_at = datetime.now(timezone.utc)
    await session.execute(
        update(JobDispatch)
        .where(
            JobDispatch.job_id == job.id,
            JobDispatch.kind == "generation",
            JobDispatch.operation_id == job.id,
            JobDispatch.state != "completed",
        )
        .values(state="cancelled", publisher_token=None, publisher_lease_until=None)
    )
    analytics_user = await _analytics_user(session, job.user_id)
    if analytics_user is not None:
        ordinal = await _generation_ordinal(session, job)
        reason_code = "cancelled" if status in {"cancelled", "canceled"} else "pipeline"
        await append_server_event_safely(
            session,
            event_name="generation_failed",
            user=analytics_user,
            properties={
                "operation_kind": "generation",
                "generation_ordinal": ordinal,
                "reason_code": reason_code,
            },
            idempotency_key=f"job:{job.id}:generation-failed",
            occurred_at=job.generation_refunded_at,
        )
        if refund_amount > 0:
            await append_server_event_safely(
                session,
                event_name="credit_balance_changed",
                user=analytics_user,
                properties={"reason": "generation_refund", "delta": refund_amount},
                idempotency_key=f"job:{job.id}:generation-refund",
                occurred_at=job.generation_refunded_at,
            )
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
        await session.execute(
            update(JobDispatch)
            .where(
                JobDispatch.job_id == job.id,
                JobDispatch.kind == "generation",
                JobDispatch.operation_id == job.id,
                JobDispatch.state != "cancelled",
            )
            .values(state="completed", publisher_token=None, publisher_lease_until=None)
        )
        analytics_user = await _analytics_user(session, job.user_id)
        if analytics_user is not None:
            generation_ordinal = await _generation_ordinal(session, job)
            await claim_referral_activation_reward(
                session,
                analytics_user,
                job,
                job.completed_at,
            )
            await append_server_event_safely(
                session,
                event_name="generation_completed",
                user=analytics_user,
                properties={
                    "operation_kind": "generation",
                    "generation_ordinal": generation_ordinal,
                },
                idempotency_key=f"job:{job.id}:generation-completed",
                occurred_at=job.completed_at,
            )
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
        await set_credit_ledger_context(
            session,
            origin="rerender_debit",
            reason="rerender operation reserved",
            idempotency_key=f"rerender:{operation_id}:debit",
            job_id=job.id,
            operation_id=operation_id,
        )
        debit = await session.execute(
            update(User)
            .where(User.id == user_id, User.email_verified.is_(True), User.credits >= cost)
            .values(credits=User.credits - cost)
        )
        if debit.rowcount == 0:
            raise InsufficientCredits("Insufficient credits")

    now = datetime.now(timezone.utc)
    job.rerender_operation_id = operation_id
    job.legacy_rerender_task_id = None
    job.rerender_state = "debited"
    job.rerender_cost = cost
    job.rerender_pending_credits = snapshot
    job.rerender_debited_at = now
    job.rerender_dispatched_at = None
    job.pending_credits = 0.0
    analytics_user = await _analytics_user(session, job.user_id)
    if analytics_user is not None:
        await append_server_event_safely(
            session,
            event_name="generation_requested",
            user=analytics_user,
            properties={
                "operation_kind": "rerender",
                "credit_cost": cost,
                "generation_ordinal": "repeat",
            },
            idempotency_key=f"rerender:{operation_id}:requested",
            occurred_at=now,
        )
        if cost > 0:
            await append_server_event_safely(
                session,
                event_name="credit_balance_changed",
                user=analytics_user,
                properties={"reason": "rerender_debit", "delta": -cost},
                idempotency_key=f"rerender:{operation_id}:debit",
                occurred_at=now,
            )
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
    await session.execute(
        update(JobDispatch)
        .where(
            JobDispatch.job_id == job.id,
            JobDispatch.kind == "rerender",
            JobDispatch.operation_id == operation_id,
            JobDispatch.state != "cancelled",
        )
        .values(state="completed", publisher_token=None, publisher_lease_until=None)
    )
    analytics_user = await _analytics_user(session, job.user_id)
    if analytics_user is not None:
        await append_server_event_safely(
            session,
            event_name="generation_completed",
            user=analytics_user,
            properties={"operation_kind": "rerender", "generation_ordinal": "repeat"},
            idempotency_key=f"rerender:{operation_id}:completed",
            occurred_at=datetime.now(timezone.utc),
        )
    return True


async def refund_rerender(
    session: AsyncSession,
    job_id: uuid.UUID | str,
    operation_id: uuid.UUID,
    *,
    require_undispatched: bool = False,
    outbox_dispatch_id: uuid.UUID | None = None,
    allow_claimed_outbox: bool = False,
) -> bool:
    """Refund one exact active rerender and restore its fractional snapshot."""
    result = await session.execute(
        select(Job).where(Job.id == job_id).with_for_update().execution_options(populate_existing=True)
    )
    job = result.scalar_one_or_none()
    dispatch = (
        await _lock_operation_dispatch(
            session,
            job_id=job.id,
            operation_id=operation_id,
            kind="rerender",
            dispatch_id=outbox_dispatch_id,
        )
        if job is not None
        else None
    )
    dispatch_allowed = _dispatch_allows_refund(
        dispatch,
        explicit_dispatch=outbox_dispatch_id is not None,
        require_undispatched=require_undispatched,
        allow_claimed=allow_claimed_outbox,
    )
    if (
        job is None
        or job.rerender_operation_id != operation_id
        or job.rerender_state not in {"debited", "dispatched", "running"}
        or not dispatch_allowed
        or (
            require_undispatched
            and dispatch is None
            and (job.rerender_state != "debited" or job.rerender_dispatched_at is not None)
        )
    ):
        return False

    refund_cost = dispatch.debited_credits if dispatch is not None else job.rerender_cost
    pending_snapshot = dispatch.pending_credits_snapshot if dispatch is not None else job.rerender_pending_credits
    if refund_cost < 0 or pending_snapshot < 0:
        return False
    if refund_cost > 0:
        await set_credit_ledger_context(
            session,
            origin="rerender_refund",
            reason="undelivered rerender refunded",
            idempotency_key=f"rerender:{operation_id}:refund",
            job_id=job.id,
            operation_id=operation_id,
        )
        await session.execute(update(User).where(User.id == job.user_id).values(credits=User.credits + refund_cost))
    await session.execute(
        update(Job)
        .where(Job.id == job.id)
        .values(pending_credits=func.coalesce(Job.pending_credits, 0.0) + pending_snapshot)
    )
    job.rerender_state = "refunded"
    await session.execute(
        update(JobDispatch)
        .where(
            JobDispatch.job_id == job.id,
            JobDispatch.kind == "rerender",
            JobDispatch.operation_id == operation_id,
            JobDispatch.state != "completed",
        )
        .values(state="cancelled", publisher_token=None, publisher_lease_until=None)
    )
    analytics_user = await _analytics_user(session, job.user_id)
    if analytics_user is not None:
        failed_at = datetime.now(timezone.utc)
        await append_server_event_safely(
            session,
            event_name="generation_failed",
            user=analytics_user,
            properties={
                "operation_kind": "rerender",
                "generation_ordinal": "repeat",
                "reason_code": "pipeline",
            },
            idempotency_key=f"rerender:{operation_id}:failed",
            occurred_at=failed_at,
        )
        if refund_cost > 0:
            await append_server_event_safely(
                session,
                event_name="credit_balance_changed",
                user=analytics_user,
                properties={"reason": "rerender_refund", "delta": refund_cost},
                idempotency_key=f"rerender:{operation_id}:refund",
                occurred_at=failed_at,
            )
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


async def complete_locked_rerender(
    session: AsyncSession,
    job: Job,
    operation_id: uuid.UUID | None,
) -> bool:
    """Complete the exact operation while its publication row lock is still held."""
    if job.rerender_state != "running":
        return False
    if operation_id is None:
        if job.rerender_operation_id is not None:
            return False
    elif job.rerender_operation_id != operation_id:
        return False
    job.rerender_state = "completed"
    if operation_id is not None:
        await session.execute(
            update(JobDispatch)
            .where(
                JobDispatch.job_id == job.id,
                JobDispatch.kind == "rerender",
                JobDispatch.operation_id == operation_id,
                JobDispatch.state != "cancelled",
            )
            .values(state="completed", publisher_token=None, publisher_lease_until=None)
        )
        analytics_user = await _analytics_user(session, job.user_id)
        if analytics_user is not None:
            await append_server_event_safely(
                session,
                event_name="generation_completed",
                user=analytics_user,
                properties={"operation_kind": "rerender", "generation_ordinal": "repeat"},
                idempotency_key=f"rerender:{operation_id}:completed",
                occurred_at=datetime.now(timezone.utc),
            )
    return True


async def claim_legacy_rerender(
    session: AsyncSession,
    job_id: uuid.UUID | str,
    *,
    cost: int,
    task_id: str,
) -> bool:
    """Persist the Redis-only cost before a pre-deploy task starts rendering."""
    if cost <= 0 or not task_id or len(task_id) > 255:
        return False
    result = await session.execute(
        select(Job).where(Job.id == job_id).with_for_update().execution_options(populate_existing=True)
    )
    job = result.scalar_one_or_none()
    if job is None or job.rerender_operation_id is not None:
        return False
    if job.rerender_state == "running":
        return job.legacy_rerender_task_id == task_id and job.rerender_cost == cost
    if job.rerender_state != "idle":
        return False
    job.rerender_state = "running"
    job.rerender_cost = cost
    job.legacy_rerender_task_id = task_id
    job.rerender_debited_at = job.rerender_debited_at or datetime.now(timezone.utc)
    return True


async def refund_legacy_rerender(session: AsyncSession, job_id: uuid.UUID | str) -> int:
    """Refund and terminalize one claimed legacy rerender in the same transaction."""
    result = await session.execute(
        select(Job).where(Job.id == job_id).with_for_update().execution_options(populate_existing=True)
    )
    job = result.scalar_one_or_none()
    if (
        job is None
        or job.rerender_operation_id is not None
        or job.rerender_state != "running"
        or job.rerender_cost <= 0
    ):
        return 0

    refund_cost = int(job.rerender_cost)
    await set_credit_ledger_context(
        session,
        origin="legacy_rerender_refund",
        reason="legacy rerender failure refunded",
        idempotency_key=f"legacy-rerender:{job.id}:refund",
        job_id=job.id,
        operation_id=job.id,
    )
    await session.execute(update(User).where(User.id == job.user_id).values(credits=User.credits + refund_cost))
    job.pending_credits = float(job.pending_credits or 0.0) + refund_cost
    job.rerender_state = "refunded"

    analytics_user = await _analytics_user(session, job.user_id)
    if analytics_user is not None:
        refunded_at = datetime.now(timezone.utc)
        await append_server_event_safely(
            session,
            event_name="generation_failed",
            user=analytics_user,
            properties={
                "operation_kind": "rerender",
                "generation_ordinal": "repeat",
                "reason_code": "pipeline",
            },
            idempotency_key=f"legacy-rerender:{job.id}:failed",
            occurred_at=refunded_at,
        )
        await append_server_event_safely(
            session,
            event_name="credit_balance_changed",
            user=analytics_user,
            properties={"reason": "rerender_refund", "delta": refund_cost},
            idempotency_key=f"legacy-rerender:{job.id}:refund",
            occurred_at=refunded_at,
        )
    return refund_cost


async def finish_legacy_rerender(
    session: AsyncSession,
    job_id: uuid.UUID | str,
    *,
    state: str,
) -> bool:
    """Complete a claimed legacy task; refunds use the atomic refund helper."""
    if state != "completed":
        raise ValueError("Invalid legacy rerender terminal state")
    result = await session.execute(
        select(Job).where(Job.id == job_id).with_for_update().execution_options(populate_existing=True)
    )
    job = result.scalar_one_or_none()
    if job is None or job.rerender_operation_id is not None or job.rerender_state != "running":
        return False
    job.rerender_state = state
    return True
