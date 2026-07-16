from __future__ import annotations

import asyncio
import os
import re
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import asyncpg
import pytest
import pytest_asyncio
from pydantic import SecretStr
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db.base import Base
from app.db.models import MetaConversionOutbox, User
from app.marketing.meta_capi import dispatch_pending_meta_conversions, enqueue_meta_conversion

_ADMIN_DSN = os.getenv(
    "POSTGRES_MARKETING_TEST_ADMIN_DSN",
    "postgresql://clipia:clipia_dev@localhost:5435/postgres",
)


def _require_postgres_tests() -> None:
    if os.getenv("RUN_POSTGRES_MARKETING_TESTS") != "1":
        pytest.skip("set RUN_POSTGRES_MARKETING_TESTS=1 to run real PostgreSQL Meta outbox tests")


@pytest_asyncio.fixture
async def postgres_meta_sessions() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    _require_postgres_tests()
    database_name = f"clipia_meta_test_{uuid.uuid4().hex[:12]}"
    assert re.fullmatch(r"clipia_meta_test_[0-9a-f]{12}", database_name)
    admin = await asyncpg.connect(_ADMIN_DSN)
    await admin.execute(f'CREATE DATABASE "{database_name}"')
    database_url = f"postgresql+asyncpg://clipia:clipia_dev@localhost:5435/{database_name}"
    engine = create_async_engine(database_url, pool_size=5, max_overflow=5)
    sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        yield sessions
    finally:
        await engine.dispose()
        await admin.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = $1 AND pid <> pg_backend_pid()",
            database_name,
        )
        await admin.execute(f'DROP DATABASE "{database_name}"')
        await admin.close()


def _configure_meta(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "META_CAPI_ENABLED", True)
    monkeypatch.setattr(settings, "META_CAPI_PIXEL_ID", "pixel-postgres")
    monkeypatch.setattr(settings, "META_CAPI_ACCESS_TOKEN", SecretStr("postgres-access-token"))
    monkeypatch.setattr(settings, "META_CAPI_API_VERSION", "v23.0")
    monkeypatch.setattr(settings, "MARKETING_PSEUDONYM_SECRET", SecretStr("postgres-pseudonym-secret"))


class _Response:
    def raise_for_status(self) -> None:
        return None


class _Client:
    def __init__(self, *, failure: Exception | None = None) -> None:
        self.calls = 0
        self.failure = failure

    async def post(self, *_args: object, **_kwargs: object) -> _Response:
        self.calls += 1
        if self.failure is not None:
            raise self.failure
        return _Response()


async def _seed_event(sessions: async_sessionmaker[AsyncSession]) -> tuple[uuid.UUID, uuid.UUID]:
    async with sessions() as db:
        user = User(
            email=f"meta-pg-{uuid.uuid4().hex}@example.com",
            name="Meta PostgreSQL",
            password_hash="test",
            credits=0,
            email_verified=True,
            referral_code=uuid.uuid4().hex[:8],
            marketing_measurement_consented_at=datetime.now(timezone.utc),
        )
        db.add(user)
        await db.flush()
        assert await enqueue_meta_conversion(
            db,
            user=user,
            event_name="CompleteRegistration",
            event_id=f"complete-registration:{user.id}",
        )
        await db.commit()
        row = await db.scalar(select(MetaConversionOutbox))
        assert row is not None
        return user.id, row.id


@pytest.mark.asyncio
async def test_postgres_dispatch_skips_locked_outbox_row(
    postgres_meta_sessions: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_meta(monkeypatch)
    sessions = postgres_meta_sessions
    _user_id, row_id = await _seed_event(sessions)
    client = _Client()

    async with sessions() as holder:
        await holder.execute(select(MetaConversionOutbox).where(MetaConversionOutbox.id == row_id).with_for_update())
        async with sessions() as skipped:
            result = await asyncio.wait_for(
                dispatch_pending_meta_conversions(skipped, client=client),
                timeout=2,
            )
            assert result == {"sent": 0, "retried": 0, "failed": 0, "cancelled": 0, "unsupported": 0}
            assert client.calls == 0
        await holder.rollback()

    async with sessions() as delivered:
        result = await dispatch_pending_meta_conversions(delivered, client=client)
        assert result == {"sent": 1, "retried": 0, "failed": 0, "cancelled": 0, "unsupported": 0}
        assert client.calls == 1
    async with sessions() as repeated:
        repeated_result = await dispatch_pending_meta_conversions(repeated, client=client)
        assert repeated_result == {"sent": 0, "retried": 0, "failed": 0, "cancelled": 0, "unsupported": 0}
        assert client.calls == 1


@pytest.mark.asyncio
async def test_postgres_dispatch_revalidates_revoked_consent_before_network(
    postgres_meta_sessions: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_meta(monkeypatch)
    sessions = postgres_meta_sessions
    user_id, row_id = await _seed_event(sessions)
    async with sessions() as revoke:
        await revoke.execute(update(User).where(User.id == user_id).values(marketing_measurement_consented_at=None))
        await revoke.commit()
    client = _Client()

    async with sessions() as dispatch:
        result = await dispatch_pending_meta_conversions(dispatch, client=client)

    assert result == {"sent": 0, "retried": 0, "failed": 0, "cancelled": 1, "unsupported": 0}
    assert client.calls == 0
    async with sessions() as verify:
        row = await verify.get(MetaConversionOutbox, row_id)
        assert row is not None and row.status == "cancelled" and row.last_error == "consent_revoked"


@pytest.mark.asyncio
async def test_postgres_dispatch_failure_persists_retry_without_losing_event(
    postgres_meta_sessions: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_meta(monkeypatch)
    sessions = postgres_meta_sessions
    _user_id, row_id = await _seed_event(sessions)
    client = _Client(failure=TimeoutError("network unavailable"))

    async with sessions() as dispatch:
        result = await dispatch_pending_meta_conversions(dispatch, client=client)

    assert result == {"sent": 0, "retried": 1, "failed": 0, "cancelled": 0, "unsupported": 0}
    assert client.calls == 1
    async with sessions() as verify:
        row = await verify.get(MetaConversionOutbox, row_id)
        assert row is not None and row.status == "retry" and row.attempts == 1


@pytest.mark.asyncio
async def test_postgres_concurrent_same_event_id_inserts_once(
    postgres_meta_sessions: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_meta(monkeypatch)
    sessions = postgres_meta_sessions
    async with sessions() as seed:
        user = User(
            email=f"meta-pg-race-{uuid.uuid4().hex}@example.com",
            name="Meta PostgreSQL Race",
            password_hash="test",
            credits=0,
            email_verified=True,
            referral_code=uuid.uuid4().hex[:8],
            marketing_measurement_consented_at=datetime.now(timezone.utc),
        )
        seed.add(user)
        await seed.commit()
    event_id = f"complete-registration:{user.id}"

    async def attempt() -> bool:
        async with sessions() as db:
            inserted = await enqueue_meta_conversion(
                db,
                user=user,
                event_name="CompleteRegistration",
                event_id=event_id,
            )
            await db.commit()
            return inserted

    outcomes = await asyncio.gather(attempt(), attempt())
    assert sorted(outcomes) == [False, True]
    async with sessions() as verify:
        rows = list(await verify.scalars(select(MetaConversionOutbox)))
        assert len(rows) == 1
