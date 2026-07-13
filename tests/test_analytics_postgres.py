import asyncio
import os
import re
import uuid
from datetime import datetime, timezone

import asyncpg
import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.analytics.schemas import AnalyticsBatch
from app.analytics.service import ingest_client_events
from app.config import settings
from app.db.models import AnalyticsEvent

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


def test_postgres_analytics_concurrency_append_only_and_migration_round_trip(monkeypatch):
    if os.getenv("RUN_POSTGRES_PAYMENT_TESTS") != "1":
        pytest.skip("set RUN_POSTGRES_PAYMENT_TESTS=1 to run real PostgreSQL analytics tests")

    database_name = f"clipia_analytics_test_{uuid.uuid4().hex[:12]}"
    assert re.fullmatch(r"clipia_analytics_test_[0-9a-f]{12}", database_name)
    database_url = f"postgresql+asyncpg://clipia:clipia_dev@localhost:5435/{database_name}"
    asyncio.run(_create_database(database_name))
    try:
        monkeypatch.setattr(settings, "DATABASE_URL", database_url)
        config = Config("alembic.ini")
        command.upgrade(config, "head")

        event_id = uuid.uuid4()
        batch = AnalyticsBatch.model_validate(
            {
                "events": [
                    {
                        "event_id": str(event_id),
                        "event_name": "landing_viewed",
                        "schema_version": 1,
                        "occurred_at": datetime.now(timezone.utc).isoformat(),
                        "anonymous_session_id": str(uuid.uuid4()),
                        "page": "landing",
                        "device_class": "desktop",
                        "properties": {"landing_variant": "control", "niche": None},
                    }
                ]
            }
        )

        async def exercise_store():
            engine = create_async_engine(database_url, pool_size=4, max_overflow=4)
            sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

            async def ingest_once():
                async with sessions() as session:
                    return await ingest_client_events(session, batch, None)

            results = await asyncio.gather(ingest_once(), ingest_once())
            assert sorted(results) == [(0, 1), (1, 0)]

            async with sessions() as session:
                assert await session.scalar(sa.select(sa.func.count()).select_from(AnalyticsEvent)) == 1
                with pytest.raises(sa.exc.DBAPIError, match="append-only"):
                    await session.execute(
                        sa.update(AnalyticsEvent).where(AnalyticsEvent.event_id == event_id).values(page="blog")
                    )
                    await session.commit()
                await session.rollback()

                with pytest.raises(sa.exc.DBAPIError, match="append-only"):
                    await session.execute(sa.delete(AnalyticsEvent).where(AnalyticsEvent.event_id == event_id))
                    await session.commit()
                await session.rollback()
                assert await session.scalar(sa.select(sa.func.count()).select_from(AnalyticsEvent)) == 1

            await engine.dispose()

        asyncio.run(exercise_store())

        command.downgrade(config, "e1f2a3b4c5d6")

        async def inspect_state() -> tuple[str, bool, bool]:
            connection = await asyncpg.connect(f"postgresql://clipia:clipia_dev@localhost:5435/{database_name}")
            try:
                revision = await connection.fetchval("SELECT version_num FROM alembic_version")
                table_exists = await connection.fetchval("SELECT to_regclass('public.analytics_events') IS NOT NULL")
                trigger_exists = await connection.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM pg_trigger "
                    "WHERE tgname = 'analytics_events_append_only' AND NOT tgisinternal)"
                )
                return revision, table_exists, trigger_exists
            finally:
                await connection.close()

        assert asyncio.run(inspect_state()) == ("e1f2a3b4c5d6", False, False)

        command.upgrade(config, "head")
        assert asyncio.run(inspect_state()) == ("f3a4b5c6d7e8", True, True)
    finally:
        asyncio.run(_drop_database(database_name))
