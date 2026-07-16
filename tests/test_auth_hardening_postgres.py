import asyncio
import os
import re
import uuid
from datetime import datetime, timedelta, timezone

import asyncpg
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.reset_tokens import consume_password_reset_token
from app.auth.service import hash_password
from app.config import settings
from app.db.models import PasswordResetToken, User
from tests.migration_contract import EXPECTED_ALEMBIC_HEAD

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


def test_postgres_reset_token_is_consumed_exactly_once_and_migration_round_trips(monkeypatch):
    if os.getenv("RUN_POSTGRES_PAYMENT_TESTS") != "1":
        pytest.skip("set RUN_POSTGRES_PAYMENT_TESTS=1 to run real PostgreSQL auth tests")

    database_name = f"clipia_auth_test_{uuid.uuid4().hex[:12]}"
    assert re.fullmatch(r"clipia_auth_test_[0-9a-f]{12}", database_name)
    database_url = f"postgresql+asyncpg://clipia:clipia_dev@localhost:5435/{database_name}"
    asyncio.run(_create_database(database_name))
    try:
        monkeypatch.setattr(settings, "DATABASE_URL", database_url)
        config = Config("alembic.ini")
        command.upgrade(config, "head")

        async def exercise_token() -> None:
            engine = create_async_engine(database_url, pool_size=4, max_overflow=4)
            sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            now = datetime.now(timezone.utc)
            user_id = uuid.uuid4()
            jti = uuid.uuid4()
            async with sessions() as session:
                session.add(
                    User(
                        id=user_id,
                        email=f"{user_id}@example.com",
                        name="Reset User",
                        password_hash=hash_password("Secret123"),
                        credits=0,
                        referral_code=uuid.uuid4().hex[:8],
                    )
                )
                await session.commit()
                session.add(
                    PasswordResetToken(
                        jti=jti,
                        user_id=user_id,
                        issued_at=now,
                        expires_at=now + timedelta(minutes=10),
                    )
                )
                await session.commit()

            async def consume_once() -> bool:
                async with sessions() as session:
                    consumed = await consume_password_reset_token(
                        session,
                        user_id=user_id,
                        jti=jti,
                        used_at=datetime.now(timezone.utc),
                    )
                    await session.commit()
                    return consumed

            results = await asyncio.gather(consume_once(), consume_once())
            assert sorted(results) == [False, True]
            async with sessions() as session:
                stored = await session.get(PasswordResetToken, jti)
                assert stored is not None and stored.used_at is not None
            await engine.dispose()

        asyncio.run(exercise_token())
        command.downgrade(config, "f3a4b5c6d7e8")

        async def inspect_state() -> tuple[str, bool, bool]:
            connection = await asyncpg.connect(f"postgresql://clipia:clipia_dev@localhost:5435/{database_name}")
            try:
                revision = await connection.fetchval("SELECT version_num FROM alembic_version")
                token_table = await connection.fetchval(
                    "SELECT to_regclass('public.password_reset_tokens') IS NOT NULL"
                )
                consent_column = await connection.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name='users' AND column_name='consent_terms_version')"
                )
                return revision, token_table, consent_column
            finally:
                await connection.close()

        assert asyncio.run(inspect_state()) == ("f3a4b5c6d7e8", False, False)
        command.upgrade(config, "head")
        assert asyncio.run(inspect_state()) == (EXPECTED_ALEMBIC_HEAD, True, True)
    finally:
        asyncio.run(_drop_database(database_name))
