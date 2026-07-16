import asyncio
import os
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import asyncpg
import pytest
import pytest_asyncio
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth import routes as auth_routes
from app.config import settings
from app.db.engine import get_db
from app.db.models import AcquisitionReward, CreditLedgerEntry, Job, MarketingOffer, User
from app.main import create_app
from app.services.acquisition_rewards import claim_campaign_reward, claim_referral_activation_reward

_ADMIN_DSN = os.getenv(
    "POSTGRES_PAYMENT_TEST_ADMIN_DSN",
    "postgresql://clipia:clipia_dev@localhost:5435/postgres",
)


def _require_postgres_tests() -> None:
    if os.getenv("RUN_POSTGRES_PAYMENT_TESTS") != "1":
        pytest.skip("set RUN_POSTGRES_PAYMENT_TESTS=1 to run real PostgreSQL growth reward races")


def _database_urls(database_name: str) -> tuple[str, str]:
    admin_url = sa.engine.make_url(_ADMIN_DSN)
    direct_url = admin_url.set(drivername="postgresql", database=database_name)
    async_url = admin_url.set(drivername="postgresql+asyncpg", database=database_name)
    return (
        async_url.render_as_string(hide_password=False),
        direct_url.render_as_string(hide_password=False),
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


@pytest.fixture(scope="module")
def postgres_growth_database():
    _require_postgres_tests()
    database_name = f"clipia_growth_test_{uuid.uuid4().hex[:12]}"
    assert re.fullmatch(r"clipia_growth_test_[0-9a-f]{12}", database_name)
    database_url, direct_dsn = _database_urls(database_name)
    previous = (settings.DATABASE_URL, settings.CREDIT_LEDGER_MODE, settings.ANALYTICS_ENABLED)

    asyncio.run(_create_database(database_name))
    try:
        settings.DATABASE_URL = database_url
        settings.CREDIT_LEDGER_MODE = "shadow"
        settings.ANALYTICS_ENABLED = False
        command.upgrade(Config("alembic.ini"), "head")
        yield {"database_url": database_url, "direct_dsn": direct_dsn}
    finally:
        settings.DATABASE_URL, settings.CREDIT_LEDGER_MODE, settings.ANALYTICS_ENABLED = previous
        asyncio.run(_drop_database(database_name))


@pytest_asyncio.fixture
async def postgres_growth_sessions(postgres_growth_database):
    engine = create_async_engine(postgres_growth_database["database_url"], pool_size=10, max_overflow=10)
    sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        yield sessions
    finally:
        await engine.dispose()


def test_postgres_growth_migration_seeds_only_canonical_offer(postgres_growth_database):
    async def inspect_migration():
        connection = await asyncpg.connect(postgres_growth_database["direct_dsn"])
        try:
            revision = await connection.fetchval("SELECT version_num FROM alembic_version")
            offer = await connection.fetchrow("SELECT code, bonus_credits, is_active, expires_at FROM marketing_offers")
            columns = await connection.fetch(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'users'"
            )
            index_definition = await connection.fetchval(
                "SELECT indexdef FROM pg_indexes "
                "WHERE schemaname = 'public' AND indexname = 'uq_acquisition_reward_user_acquisition'"
            )
            return revision, offer, {row["column_name"] for row in columns}, index_definition
        finally:
            await connection.close()

    revision, offer, user_columns, index_definition = asyncio.run(inspect_migration())
    assert revision == "f9a0b1c2d3e4"
    assert dict(offer) == {
        "code": "creator20_v1",
        "bonus_credits": 18,
        "is_active": True,
        "expires_at": None,
    }
    assert {"acquisition_offer_id", "marketing_measurement_consented_at"}.issubset(user_columns)
    assert "WHERE" in index_definition
    assert "campaign_signup" in index_definition
    assert "referral_activation" in index_definition


@pytest.mark.asyncio
async def test_postgres_two_verifications_claim_once_and_write_distinct_real_ledger_entries(
    postgres_growth_sessions,
    monkeypatch,
):
    sessions = postgres_growth_sessions
    async with sessions() as seed:
        offer_id = await seed.scalar(sa.select(MarketingOffer.id).where(MarketingOffer.code == "creator20_v1"))
        user = User(
            email=f"postgres-campaign-{uuid.uuid4().hex}@example.com",
            name="PostgreSQL Campaign",
            password_hash="hashed",
            credits=0,
            email_verified=False,
            verification_code="123456",
            verification_expires=datetime.now(timezone.utc) + timedelta(minutes=10),
            acquisition_offer_id=offer_id,
        )
        seed.add(user)
        await seed.commit()
        user_id = user.id

    @asynccontextmanager
    async def no_process_lock():
        yield

    monkeypatch.setattr(auth_routes, "get_lock", lambda _key: no_process_lock())
    monkeypatch.setattr(auth_routes, "send_welcome_email", lambda *_args: True)
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", False)

    async def override_get_db():
        async with sessions() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app, client=("127.0.0.10", 50000), raise_app_exceptions=False)
    async with (
        AsyncClient(transport=transport, base_url="http://testserver") as first,
        AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as second,
    ):
        responses = await asyncio.gather(
            first.post("/api/v1/auth/verify-email", json={"email": user.email, "code": "123456"}),
            second.post("/api/v1/auth/verify-email", json={"email": user.email, "code": "123456"}),
        )

    assert [response.status_code for response in responses] == [200, 200]
    assert sorted(response.json()["status"] for response in responses) == ["already_verified", "verified"]
    async with sessions() as verification:
        persisted = await verification.get(User, user_id)
        reward = await verification.scalar(sa.select(AcquisitionReward).where(AcquisitionReward.user_id == user_id))
        entries = list(
            await verification.scalars(
                sa.select(CreditLedgerEntry)
                .where(CreditLedgerEntry.user_id == user_id)
                .order_by(CreditLedgerEntry.balance_after)
            )
        )

    assert persisted is not None and persisted.credits == 20
    assert reward is not None and reward.credits == 18
    assert [(entry.delta, entry.origin, entry.balance_after) for entry in entries] == [
        (2, "welcome_bonus", 2),
        (18, "campaign_signup_reward", 20),
    ]
    assert [entry.idempotency_key for entry in entries] == [
        f"welcome:{user_id}",
        f"acquisition:{user_id}:campaign_signup",
    ]
    assert entries[0].operation_id is None
    assert entries[1].operation_id == reward.id
    assert entries[0].idempotency_key != entries[1].idempotency_key


async def _seed_referral_activation(sessions, referrer_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    async with sessions() as seed:
        referred = User(
            email=f"postgres-referred-{uuid.uuid4().hex}@example.com",
            name="PostgreSQL Referred",
            password_hash="hashed",
            credits=0,
            email_verified=True,
            referred_by=referrer_id,
        )
        seed.add(referred)
        await seed.flush()
        job = Job(
            user_id=referred.id,
            topic="PostgreSQL referral activation",
            style="educational",
            duration_target=30,
            status="editable",
            video_url=f"/storage/output/{uuid.uuid4()}.mp4",
            completed_at=datetime.now(timezone.utc),
        )
        seed.add(job)
        await seed.commit()
        return referred.id, job.id


@pytest.mark.asyncio
async def test_postgres_two_referral_activations_credit_the_referrer_once(postgres_growth_sessions):
    sessions = postgres_growth_sessions
    async with sessions() as seed:
        referrer = User(
            email=f"postgres-referrer-{uuid.uuid4().hex}@example.com",
            name="PostgreSQL Referrer",
            password_hash="hashed",
            credits=0,
            email_verified=True,
        )
        seed.add(referrer)
        await seed.commit()
        referrer_id = referrer.id
    candidates = [await _seed_referral_activation(sessions, referrer_id) for _index in range(2)]

    async def activate(referred_id: uuid.UUID, job_id: uuid.UUID) -> int:
        async with sessions() as session:
            referred = await session.get(User, referred_id)
            job = await session.get(Job, job_id)
            result = await claim_referral_activation_reward(session, referred, job, job.completed_at)
            await session.commit()
            return result

    results = await asyncio.gather(*(activate(referred_id, job_id) for referred_id, job_id in candidates))

    assert sorted(results) == [0, 18]
    async with sessions() as verification:
        assert (await verification.get(User, referrer_id)).credits == 18
        rewards = list(
            await verification.scalars(sa.select(AcquisitionReward).where(AcquisitionReward.user_id == referrer_id))
        )
    assert len(rewards) == 1
    assert rewards[0].reward_type == "referral_activation"


@pytest.mark.asyncio
async def test_postgres_campaign_and_referral_race_preserves_acquisition_exclusivity(postgres_growth_sessions):
    sessions = postgres_growth_sessions
    async with sessions() as seed:
        offer_id = await seed.scalar(sa.select(MarketingOffer.id).where(MarketingOffer.code == "creator20_v1"))
        recipient = User(
            email=f"postgres-exclusive-{uuid.uuid4().hex}@example.com",
            name="PostgreSQL Exclusive",
            password_hash="hashed",
            credits=0,
            email_verified=True,
            acquisition_offer_id=offer_id,
        )
        seed.add(recipient)
        await seed.commit()
        recipient_id = recipient.id
    referred_id, job_id = await _seed_referral_activation(sessions, recipient_id)

    async def claim_campaign() -> int:
        async with sessions() as session:
            recipient = await session.get(User, recipient_id)
            result = await claim_campaign_reward(session, recipient, datetime.now(timezone.utc))
            await session.commit()
            return result

    async def activate_referral() -> int:
        async with sessions() as session:
            referred = await session.get(User, referred_id)
            job = await session.get(Job, job_id)
            result = await claim_referral_activation_reward(session, referred, job, job.completed_at)
            await session.commit()
            return result

    results = await asyncio.gather(claim_campaign(), activate_referral())

    assert sorted(results) == [0, 18]
    async with sessions() as verification:
        assert (await verification.get(User, recipient_id)).credits == 18
        rewards = list(
            await verification.scalars(sa.select(AcquisitionReward).where(AcquisitionReward.user_id == recipient_id))
        )
    assert len(rewards) == 1
    assert rewards[0].reward_type in {"campaign_signup", "referral_activation"}
