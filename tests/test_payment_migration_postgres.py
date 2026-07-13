import asyncio
import os
import re
import uuid

import asyncpg
import pytest

from alembic import command
from alembic.config import Config
from app.config import settings

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
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity " "WHERE datname = $1 AND pid <> pg_backend_pid()",
            database_name,
        )
        await connection.execute(f'DROP DATABASE "{database_name}"')
    finally:
        await connection.close()


def test_postgres_migration_upgrades_from_dispatch_outbox_head(monkeypatch):
    if os.getenv("RUN_POSTGRES_PAYMENT_TESTS") != "1":
        pytest.skip("set RUN_POSTGRES_PAYMENT_TESTS=1 to run real PostgreSQL migration")

    database_name = f"clipia_payment_migration_{uuid.uuid4().hex[:12]}"
    assert re.fullmatch(r"clipia_payment_migration_[0-9a-f]{12}", database_name)
    database_url = f"postgresql+asyncpg://clipia:clipia_dev@localhost:5435/{database_name}"
    asyncio.run(_create_database(database_name))
    try:
        monkeypatch.setattr(settings, "DATABASE_URL", database_url)
        config = Config("alembic.ini")
        command.upgrade(config, "b8c9d0e1f2a3")
        command.upgrade(config, "head")

        user_id = uuid.uuid4()
        divergent_rows = [
            (uuid.uuid4(), "approved", "refunded", "refunded", "refunded"),
            (uuid.uuid4(), "refunded", "paid", "refunded", "refunded"),
            (uuid.uuid4(), "pending", "paid", "approved", "paid"),
            (uuid.uuid4(), "approved", "void", "approved", "paid"),
            (uuid.uuid4(), "pending", "void", "pending", "pending"),
        ]

        async def seed_divergent_rows():
            connection = await asyncpg.connect(f"postgresql://clipia:clipia_dev@localhost:5435/{database_name}")
            try:
                await connection.execute(
                    "INSERT INTO users (id, email, name, password_hash, credits, plan, referral_code) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7)",
                    user_id,
                    f"migration-{user_id.hex}@example.com",
                    "Migration Test",
                    "test",
                    5,
                    "free",
                    user_id.hex[:8],
                )
                await connection.executemany(
                    "INSERT INTO credit_purchases "
                    "(id, user_id, package_name, credits_amount, bonus_credits, price_brl, provider, "
                    "mp_preference_id, status, payment_state, currency) "
                    "VALUES ($1, $2, 'starter', 10, 0, 1990, 'stripe', $3, $4, $5, 'BRL')",
                    [
                        (row_id, user_id, f"checkout_{row_id.hex}", legacy_status, payment_state)
                        for row_id, legacy_status, payment_state, _expected_legacy, _expected_round_trip in divergent_rows
                    ],
                )
            finally:
                await connection.close()

        asyncio.run(seed_divergent_rows())
        command.downgrade(config, "b8c9d0e1f2a3")

        async def inspect_downgrade():
            connection = await asyncpg.connect(f"postgresql://clipia:clipia_dev@localhost:5435/{database_name}")
            try:
                columns = {
                    row["column_name"]
                    for row in await connection.fetch(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = 'public' AND table_name = 'credit_purchases'"
                    )
                }
                statuses = {
                    row["id"]: row["status"]
                    for row in await connection.fetch(
                        "SELECT id, status FROM credit_purchases WHERE user_id = $1",
                        user_id,
                    )
                }
                return columns, statuses
            finally:
                await connection.close()

        downgraded_columns, downgraded_statuses = asyncio.run(inspect_downgrade())
        assert {"payment_state", "currency", "snapshot_version", "snapshot_hash"}.isdisjoint(downgraded_columns)
        assert downgraded_statuses == {
            row_id: expected_legacy
            for row_id, _legacy, _payment_state, expected_legacy, _expected_round_trip in divergent_rows
        }

        command.upgrade(config, "head")

        async def inspect_migration():
            connection = await asyncpg.connect(f"postgresql://clipia:clipia_dev@localhost:5435/{database_name}")
            try:
                revision = await connection.fetchval("SELECT version_num FROM alembic_version")
                columns = {
                    row["column_name"]
                    for row in await connection.fetch(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = 'public' AND table_name = 'credit_purchases'"
                    )
                }
                indexes = {
                    row["indexname"]: row["indexdef"]
                    for row in await connection.fetch(
                        "SELECT indexname, indexdef FROM pg_indexes "
                        "WHERE schemaname = 'public' AND tablename = 'credit_purchases'"
                    )
                }
                round_trip_states = {
                    row["id"]: row["payment_state"]
                    for row in await connection.fetch(
                        "SELECT id, payment_state FROM credit_purchases WHERE user_id = $1",
                        user_id,
                    )
                }
                return revision, columns, indexes, round_trip_states
            finally:
                await connection.close()

        revision, columns, indexes, round_trip_states = asyncio.run(inspect_migration())
        assert revision == "c9d0e1f2a3b4"
        assert {"payment_state", "currency", "snapshot_version", "snapshot_hash"} <= columns
        assert "uq_credit_purchase_provider_checkout" in indexes
        assert "mp_preference_id IS NOT NULL" in indexes["uq_credit_purchase_provider_checkout"]
        assert "<> 'pending'::text" in indexes["uq_credit_purchase_provider_checkout"]
        assert "uq_credit_purchase_provider_payment" in indexes
        assert round_trip_states == {
            row_id: expected_round_trip
            for row_id, _legacy, _payment_state, _expected_legacy, expected_round_trip in divergent_rows
        }
    finally:
        asyncio.run(_drop_database(database_name))
