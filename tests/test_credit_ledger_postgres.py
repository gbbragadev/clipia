import asyncio
import os
import re
import uuid

import asyncpg
import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db.models import CreditLedgerEntry, User
from app.services.credit_ledger import reconcile_credit_ledger, set_credit_ledger_context

_ADMIN_DSN = os.getenv(
    "POSTGRES_PAYMENT_TEST_ADMIN_DSN",
    "postgresql://clipia:clipia_dev@localhost:5435/postgres",
)


async def _create_database(database_name: str) -> None:
    connection = await asyncpg.connect(_ADMIN_DSN)
    try:
        await connection.execute(f'CREATE DATABASE "{database_name}"')
    finally:
        await connection.close()


async def _drop_database(database_name: str) -> None:
    connection = await asyncpg.connect(_ADMIN_DSN)
    try:
        await connection.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = $1 AND pid <> pg_backend_pid()",
            database_name,
        )
        await connection.execute(f'DROP DATABASE "{database_name}"')
    finally:
        await connection.close()


def test_postgres_credit_ledger_shadow_enforce_and_migration_round_trip(monkeypatch):
    if os.getenv("RUN_POSTGRES_PAYMENT_TESTS") != "1":
        pytest.skip("set RUN_POSTGRES_PAYMENT_TESTS=1 to run real PostgreSQL ledger tests")

    database_name = f"clipia_ledger_test_{uuid.uuid4().hex[:12]}"
    assert re.fullmatch(r"clipia_ledger_test_[0-9a-f]{12}", database_name)
    database_url = f"postgresql+asyncpg://clipia:clipia_dev@localhost:5435/{database_name}"
    direct_dsn = f"postgresql://clipia:clipia_dev@localhost:5435/{database_name}"
    user_id = uuid.uuid4()
    purchase_id = uuid.uuid4()

    asyncio.run(_create_database(database_name))
    try:
        monkeypatch.setattr(settings, "DATABASE_URL", database_url)
        monkeypatch.setattr(settings, "CREDIT_LEDGER_MODE", "shadow")
        config = Config("alembic.ini")
        command.upgrade(config, "a4b5c6d7e8f9")

        async def seed_user() -> None:
            connection = await asyncpg.connect(direct_dsn)
            try:
                await connection.execute(
                    "INSERT INTO users (id, email, name, password_hash, credits, plan, referral_code) "
                    "VALUES ($1, $2, 'Ledger Test', 'test', 11, 'free', $3)",
                    user_id,
                    f"ledger-{user_id.hex}@example.com",
                    user_id.hex[:8],
                )
            finally:
                await connection.close()

        asyncio.run(seed_user())
        command.upgrade(config, "head")

        async def exercise_shadow() -> None:
            engine = create_async_engine(database_url, pool_size=2, max_overflow=2)
            sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with sessions() as session:
                backfill = await session.scalar(
                    sa.select(CreditLedgerEntry).where(CreditLedgerEntry.user_id == user_id)
                )
                assert backfill is not None
                assert (backfill.delta, backfill.origin, backfill.balance_after) == (11, "backfill", 11)

                await set_credit_ledger_context(
                    session,
                    origin="payment_credit",
                    reason="paid purchase credited",
                    idempotency_key=f"payment:{purchase_id}:paid",
                    purchase_id=purchase_id,
                )
                await session.execute(sa.update(User).where(User.id == user_id).values(credits=User.credits + 4))
                await session.commit()

                payment_entry = await session.scalar(
                    sa.select(CreditLedgerEntry).where(
                        CreditLedgerEntry.idempotency_key == f"payment:{purchase_id}:paid"
                    )
                )
                assert payment_entry is not None
                assert (
                    payment_entry.delta,
                    payment_entry.origin,
                    payment_entry.purchase_id,
                    payment_entry.balance_after,
                ) == (4, "payment_credit", purchase_id, 15)
                payment_entry_id = payment_entry.id

                result = await reconcile_credit_ledger(session)
                await session.commit()
                assert result["mismatch_count"] == 0

                with pytest.raises(sa.exc.DBAPIError, match="append-only"):
                    await session.execute(
                        sa.update(CreditLedgerEntry)
                        .where(CreditLedgerEntry.id == payment_entry_id)
                        .values(reason="tampered")
                    )
                    await session.commit()
                await session.rollback()

                with pytest.raises(sa.exc.DBAPIError, match="append-only"):
                    await session.execute(sa.delete(CreditLedgerEntry).where(CreditLedgerEntry.id == payment_entry_id))
                    await session.commit()
                await session.rollback()
            await engine.dispose()

        asyncio.run(exercise_shadow())

        monkeypatch.setattr(settings, "CREDIT_LEDGER_MODE", "enforce")
        enforce_key = f"enforce-probe:{uuid.uuid4()}"

        async def exercise_enforce() -> None:
            engine = create_async_engine(database_url, poolclass=sa.pool.NullPool)
            sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with sessions() as session:
                await set_credit_ledger_context(
                    session,
                    origin="enforce_probe",
                    reason="prove duplicate idempotency fails closed",
                    idempotency_key=enforce_key,
                )
                await session.execute(sa.update(User).where(User.id == user_id).values(credits=User.credits + 1))
                await session.commit()

            async with sessions() as session:
                await set_credit_ledger_context(
                    session,
                    origin="enforce_probe",
                    reason="prove duplicate idempotency fails closed",
                    idempotency_key=enforce_key,
                )
                with pytest.raises(sa.exc.IntegrityError):
                    await session.execute(sa.update(User).where(User.id == user_id).values(credits=User.credits + 1))
                    await session.commit()
                await session.rollback()
                assert await session.scalar(sa.select(User.credits).where(User.id == user_id)) == 16
            await engine.dispose()

        asyncio.run(exercise_enforce())
        monkeypatch.setattr(settings, "CREDIT_LEDGER_MODE", "shadow")

        command.downgrade(config, "a4b5c6d7e8f9")

        async def inspect_downgrade() -> tuple[str, bool, bool]:
            connection = await asyncpg.connect(direct_dsn)
            try:
                revision = await connection.fetchval("SELECT version_num FROM alembic_version")
                table_exists = await connection.fetchval(
                    "SELECT to_regclass('public.credit_ledger_entries') IS NOT NULL"
                )
                trigger_exists = await connection.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM pg_trigger "
                    "WHERE tgname = 'credit_ledger_users_update' AND NOT tgisinternal)"
                )
                return revision, table_exists, trigger_exists
            finally:
                await connection.close()

        assert asyncio.run(inspect_downgrade()) == ("a4b5c6d7e8f9", False, False)
        command.upgrade(config, "head")
        revision, table_exists, trigger_exists = asyncio.run(inspect_downgrade())
        assert (revision, table_exists, trigger_exists) == ("d7e8f9a0b1c2", True, True)
    finally:
        asyncio.run(_drop_database(database_name))
