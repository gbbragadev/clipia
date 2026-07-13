import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.exc import DBAPIError

from app.db.models import CreditLedgerEntry, CreditLedgerReconciliationRun, User
from app.services.credit_ledger import (
    assert_credit_ledger_mode_ready,
    ledger_enforce_ready,
    reconcile_credit_ledger,
)
from app.worker.celery_app import celery_app


@pytest.mark.asyncio
async def test_credit_projection_writes_append_only_shadow_entries(db_session, verified_user):
    entries = list(
        (
            await db_session.execute(
                select(CreditLedgerEntry)
                .where(CreditLedgerEntry.user_id == verified_user.id)
                .order_by(CreditLedgerEntry.created_at, CreditLedgerEntry.id)
            )
        )
        .scalars()
        .all()
    )
    assert [(entry.delta, entry.balance_after) for entry in entries] == [(5, 5)]

    await db_session.execute(update(User).where(User.id == verified_user.id).values(credits=User.credits + 3))
    await db_session.commit()

    entries = list(
        (
            await db_session.execute(
                select(CreditLedgerEntry)
                .where(CreditLedgerEntry.user_id == verified_user.id)
                .order_by(CreditLedgerEntry.created_at, CreditLedgerEntry.id)
            )
        )
        .scalars()
        .all()
    )
    assert sum(entry.delta for entry in entries) == 8
    projected_entry = next(entry for entry in entries if entry.delta == 3)
    assert projected_entry.balance_after == 8
    assert projected_entry.origin == "unclassified"

    with pytest.raises(DBAPIError, match="append-only"):
        await db_session.execute(
            update(CreditLedgerEntry).where(CreditLedgerEntry.id == projected_entry.id).values(reason="tampered")
        )
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_reconciliation_records_clean_and_mismatched_projection(db_session, verified_user):
    clean = await reconcile_credit_ledger(db_session)
    await db_session.commit()

    assert clean["user_count"] >= 1
    assert clean["mismatch_count"] == 0
    assert clean["is_clean"] is True

    db_session.add(
        CreditLedgerEntry(
            id=uuid.uuid4(),
            user_id=verified_user.id,
            delta=1,
            origin="test_probe",
            reason="intentional mismatch",
            idempotency_key=f"test-probe:{uuid.uuid4()}",
            balance_after=verified_user.credits + 1,
        )
    )
    await db_session.commit()

    mismatch = await reconcile_credit_ledger(db_session)
    await db_session.commit()
    assert mismatch["mismatch_count"] == 1
    assert mismatch["is_clean"] is False
    assert mismatch["max_abs_difference"] == 1
    assert mismatch["mismatches"][0]["user_id"] == str(verified_user.id)


@pytest.mark.asyncio
async def test_enforce_requires_seven_consecutive_clean_daily_runs(db_session):
    now = datetime.now(timezone.utc).replace(hour=5, minute=0, second=0, microsecond=0)
    for offset in range(7):
        db_session.add(
            CreditLedgerReconciliationRun(
                id=uuid.uuid4(),
                mode="shadow",
                user_count=10,
                mismatch_count=0,
                max_abs_difference=0,
                is_clean=True,
                details={"mismatches": []},
                created_at=now - timedelta(days=offset),
            )
        )
    await db_session.commit()

    assert await ledger_enforce_ready(db_session, now=now) is True

    total = await db_session.scalar(select(func.count()).select_from(CreditLedgerReconciliationRun))
    assert total == 7


@pytest.mark.asyncio
async def test_enforce_mode_refuses_start_without_clean_gate(db_session, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "CREDIT_LEDGER_MODE", "enforce")
    with pytest.raises(RuntimeError, match="seven consecutive clean daily reconciliations"):
        await assert_credit_ledger_mode_ready(db_session)


def test_credit_ledger_reconciliation_runs_daily_at_five_utc():
    entry = celery_app.conf.beat_schedule["reconcile-credit-ledger"]

    assert entry["task"] == "reconcile_credit_ledger"
    assert entry["schedule"].hour == {5}
    assert entry["schedule"].minute == {0}


@pytest.mark.asyncio
async def test_worker_reconciliation_persists_daily_evidence(test_db, verified_user, monkeypatch):
    import importlib

    from app.worker import tasks as worker_tasks

    db_engine = importlib.import_module("app.db.engine")
    monkeypatch.setattr(db_engine, "worker_session", test_db["session_factory"])
    result = await worker_tasks._reconcile_credit_ledger_async()

    assert result["is_clean"] is True
    assert result["mismatch_count"] == 0
    async with test_db["session_factory"]() as session:
        assert await session.scalar(select(func.count()).select_from(CreditLedgerReconciliationRun)) == 1
