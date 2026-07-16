import re
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import CreditLedgerEntry, CreditLedgerReconciliationRun, User

_ORIGIN_RE = re.compile(r"^[a-z][a-z0-9_]{1,49}$")
_MAX_RECONCILIATION_DETAILS = 100


def _normalize_uuid(value: uuid.UUID | str | None) -> str:
    if value is None:
        return ""
    return str(uuid.UUID(str(value)))


async def set_credit_ledger_context(
    session: AsyncSession,
    *,
    origin: str,
    reason: str,
    idempotency_key: str,
    purchase_id: uuid.UUID | str | None = None,
    job_id: uuid.UUID | str | None = None,
    operation_id: uuid.UUID | str | None = None,
) -> None:
    """Attach ledger metadata to subsequent credit mutations in this transaction.

    PostgreSQL triggers consume transaction-local settings. SQLite intentionally
    keeps generic metadata: its triggers exist to prove coverage and append-only
    behavior in isolated tests, not to emulate connection-local PostgreSQL state.
    """

    if not _ORIGIN_RE.fullmatch(origin):
        raise ValueError("invalid credit ledger origin")
    if not reason or len(reason) > 255:
        raise ValueError("invalid credit ledger reason")
    if not idempotency_key or len(idempotency_key) > 255:
        raise ValueError("invalid credit ledger idempotency key")

    dialect = session.get_bind().dialect.name
    if dialect == "sqlite":
        await session.execute(
            text(
                """
                SELECT clipia_set_credit_context(
                    :origin, :reason, :idempotency_key,
                    :purchase_id, :job_id, :operation_id
                )
                """
            ),
            {
                "origin": origin,
                "reason": reason,
                "idempotency_key": idempotency_key,
                "purchase_id": _normalize_uuid(purchase_id) or None,
                "job_id": _normalize_uuid(job_id) or None,
                "operation_id": _normalize_uuid(operation_id) or None,
            },
        )
        return
    if dialect != "postgresql":
        return

    await session.execute(
        text(
            """
            SELECT
                set_config('clipia.credit_origin', :origin, true),
                set_config('clipia.credit_reason', :reason, true),
                set_config('clipia.credit_idempotency_key', :idempotency_key, true),
                set_config('clipia.credit_purchase_id', :purchase_id, true),
                set_config('clipia.credit_job_id', :job_id, true),
                set_config('clipia.credit_operation_id', :operation_id, true),
                set_config('clipia.credit_ledger_mode', :mode, true)
            """
        ),
        {
            "origin": origin,
            "reason": reason,
            "idempotency_key": idempotency_key,
            "purchase_id": _normalize_uuid(purchase_id),
            "job_id": _normalize_uuid(job_id),
            "operation_id": _normalize_uuid(operation_id),
            "mode": settings.CREDIT_LEDGER_MODE,
        },
    )


async def reconcile_credit_ledger(session: AsyncSession) -> dict:
    """Compare the append-only ledger with the authoritative User.credits projection."""

    totals = (
        select(
            CreditLedgerEntry.user_id.label("user_id"),
            func.sum(CreditLedgerEntry.delta).label("ledger_balance"),
        )
        .group_by(CreditLedgerEntry.user_id)
        .subquery()
    )
    rows = (
        await session.execute(
            select(
                User.id,
                User.credits,
                func.coalesce(totals.c.ledger_balance, 0).label("ledger_balance"),
            ).outerjoin(totals, totals.c.user_id == User.id)
        )
    ).all()

    mismatches: list[dict[str, str | int]] = []
    max_abs_difference = 0
    for user_id, projection_balance, ledger_balance in rows:
        difference = int(projection_balance) - int(ledger_balance)
        if difference == 0:
            continue
        max_abs_difference = max(max_abs_difference, abs(difference))
        if len(mismatches) < _MAX_RECONCILIATION_DETAILS:
            mismatches.append(
                {
                    "user_id": str(user_id),
                    "projection_balance": int(projection_balance),
                    "ledger_balance": int(ledger_balance),
                    "difference": difference,
                }
            )

    mismatch_count = sum(
        1 for _user_id, projection_balance, ledger_balance in rows if projection_balance != ledger_balance
    )
    result = {
        "mode": settings.CREDIT_LEDGER_MODE,
        "user_count": len(rows),
        "mismatch_count": mismatch_count,
        "max_abs_difference": max_abs_difference,
        "is_clean": mismatch_count == 0,
        "mismatches": mismatches,
        "details_truncated": mismatch_count > len(mismatches),
    }
    session.add(
        CreditLedgerReconciliationRun(
            mode=settings.CREDIT_LEDGER_MODE,
            user_count=len(rows),
            mismatch_count=mismatch_count,
            max_abs_difference=max_abs_difference,
            is_clean=mismatch_count == 0,
            details={
                "mismatches": mismatches,
                "truncated": result["details_truncated"],
            },
        )
    )
    return result


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def ledger_enforce_ready(
    session: AsyncSession,
    *,
    now: datetime | None = None,
) -> bool:
    """Require one clean run on each of the last seven UTC calendar days."""

    now_utc = _as_utc(now or datetime.now(timezone.utc))
    runs = list(
        (
            await session.execute(
                select(CreditLedgerReconciliationRun)
                .where(CreditLedgerReconciliationRun.created_at <= now_utc)
                .order_by(CreditLedgerReconciliationRun.created_at.desc())
                .limit(100)
            )
        )
        .scalars()
        .all()
    )
    latest_by_date: dict = {}
    for run in runs:
        run_date = _as_utc(run.created_at).date()
        latest_by_date.setdefault(run_date, run)

    for offset in range(7):
        required_date = (now_utc - timedelta(days=offset)).date()
        run = latest_by_date.get(required_date)
        if run is None or not run.is_clean or run.mismatch_count != 0:
            return False
    return True


async def assert_credit_ledger_mode_ready(session: AsyncSession) -> None:
    """Fail startup closed when enforce is selected before its evidence gate."""

    if settings.CREDIT_LEDGER_MODE == "shadow":
        return
    if not await ledger_enforce_ready(session):
        raise RuntimeError("credit ledger enforce requires seven consecutive clean daily reconciliations")
