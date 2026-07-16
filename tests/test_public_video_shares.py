import asyncio
import hashlib
import os
import re
import uuid
from datetime import datetime, timezone

import asyncpg
import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth.service import create_access_token
from app.auth.session import AUTH_COOKIE_NAME
from app.config import settings
from app.db import models
from app.public_shares.service import create_public_share, record_qualified_view

_BROWSER_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0"}


async def _completed_job(test_db, job_factory, *, user_id=None, topic="Video publico"):
    job = await job_factory(user_id=user_id, status="completed")
    async with test_db["session_factory"]() as session:
        persisted = await session.get(models.Job, job.id)
        assert persisted is not None
        persisted.topic = topic
        persisted.completed_at = datetime.now(timezone.utc)
        # Deliberately not a filesystem path: public serving must resolve the
        # canonical output from the configured storage root, not trust this field.
        persisted.video_url = f"/storage/output/{job.id}.mp4"
        await session.commit()
    output_dir = test_db["storage_dir"] / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"{job.id}.mp4").write_bytes(b"public-video-bytes")
    return job


async def _create_share(client, job_id, user, auth_headers):
    return await client.post(
        f"/api/v1/videos/{job_id}/public-share",
        headers=auth_headers(user),
    )


def _view_payload(session_id=None, *, dwell_ms=5000, page_visible=True):
    return {
        "anonymous_session_id": str(session_id or uuid.uuid4()),
        "dwell_ms": dwell_ms,
        "page_visible": page_visible,
    }


@pytest.mark.asyncio
async def test_public_share_requires_owned_completed_video_and_is_idempotent(
    client,
    test_db,
    job_factory,
    verified_user,
    other_verified_user,
    auth_headers,
):
    queued = await job_factory(status="queued")
    assert (await _create_share(client, queued.id, verified_user, auth_headers)).status_code == 404

    other_job = await _completed_job(test_db, job_factory, user_id=other_verified_user.id)
    assert (await _create_share(client, other_job.id, verified_user, auth_headers)).status_code == 404

    job = await _completed_job(
        test_db,
        job_factory,
        topic="Tres ideias para crescer sem expor /tmp/segredo.mp4",
    )
    first = await _create_share(client, job.id, verified_user, auth_headers)
    replay = await _create_share(client, job.id, verified_user, auth_headers)

    assert first.status_code == replay.status_code == 200
    assert first.json() == replay.json()
    body = first.json()
    assert set(body) == {"token", "url", "title", "active"}
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", body["token"])
    assert body["url"] == f"{settings.FRONTEND_URL.rstrip('/')}/v/{body['token']}"
    assert body["title"] == "Tres ideias para crescer sem expor /tmp/segredo.mp4"
    assert body["active"] is True

    async with test_db["session_factory"]() as session:
        shares = list(await session.scalars(select(models.PublicVideoShare)))
    assert len(shares) == 1
    assert shares[0].token_hash == hashlib.sha256(body["token"].encode()).hexdigest()
    assert "token" not in models.PublicVideoShare.__table__.columns


@pytest.mark.asyncio
async def test_public_share_metadata_and_video_never_expose_or_trust_storage_path(
    client,
    test_db,
    job_factory,
    verified_user,
    auth_headers,
):
    job = await _completed_job(test_db, job_factory, topic="Titulo publico")
    async with test_db["session_factory"]() as session:
        persisted = await session.get(models.Job, job.id)
        assert persisted is not None
        persisted.video_url = "C:\\private\\customer\\raw-output.mp4"
        await session.commit()

    created = await _create_share(client, job.id, verified_user, auth_headers)
    assert created.status_code == 200
    token = created.json()["token"]

    metadata = await client.get(f"/api/v1/public-shares/{token}")
    assert metadata.status_code == 200
    payload = metadata.json()
    assert payload["title"] == "Titulo publico"
    assert payload["active"] is True
    assert payload["video_url"].endswith(f"/api/v1/public-shares/{token}/video")
    serialized = str(payload).lower()
    assert "storage" not in serialized
    assert "private" not in serialized
    assert "raw-output" not in serialized

    video = await client.get(f"/api/v1/public-shares/{token}/video")
    assert video.status_code == 200
    assert video.headers["content-type"].startswith("video/mp4")
    assert video.content == b"public-video-bytes"


@pytest.mark.asyncio
async def test_revoke_hides_metadata_and_video_and_republish_rotates_token(
    client,
    test_db,
    job_factory,
    verified_user,
    auth_headers,
):
    job = await _completed_job(test_db, job_factory)
    created = await _create_share(client, job.id, verified_user, auth_headers)
    token = created.json()["token"]

    revoked = await client.delete(
        f"/api/v1/videos/{job.id}/public-share",
        headers=auth_headers(verified_user),
    )
    assert revoked.status_code == 204
    assert (await client.get(f"/api/v1/public-shares/{token}")).status_code == 404
    assert (await client.get(f"/api/v1/public-shares/{token}/video")).status_code == 404
    assert (
        await client.post(
            f"/api/v1/public-shares/{token}/qualified-view",
            json=_view_payload(),
            headers=_BROWSER_HEADERS,
        )
    ).status_code == 404
    assert (
        await client.delete(
            f"/api/v1/videos/{job.id}/public-share",
            headers=auth_headers(verified_user),
        )
    ).status_code == 404

    republished = await _create_share(client, job.id, verified_user, auth_headers)
    assert republished.status_code == 200
    assert republished.json()["token"] != token


@pytest.mark.asyncio
async def test_qualified_view_rejects_short_hidden_owner_and_bot_without_consuming_session(
    client,
    test_db,
    job_factory,
    verified_user,
    auth_headers,
):
    job = await _completed_job(test_db, job_factory)
    created = await _create_share(client, job.id, verified_user, auth_headers)
    token = created.json()["token"]

    short = await client.post(
        f"/api/v1/public-shares/{token}/qualified-view",
        json=_view_payload(dwell_ms=4999),
        headers=_BROWSER_HEADERS,
    )
    hidden = await client.post(
        f"/api/v1/public-shares/{token}/qualified-view",
        json=_view_payload(page_visible=False),
        headers=_BROWSER_HEADERS,
    )
    bot = await client.post(
        f"/api/v1/public-shares/{token}/qualified-view",
        json=_view_payload(),
        headers={"User-Agent": "Googlebot/2.1 (+http://www.google.com/bot.html)"},
    )
    client.cookies.set(AUTH_COOKIE_NAME, create_access_token(str(verified_user.id)))
    owner = await client.post(
        f"/api/v1/public-shares/{token}/qualified-view",
        json=_view_payload(),
        headers=_BROWSER_HEADERS,
    )
    client.cookies.clear()

    assert [response.status_code for response in (short, hidden, bot, owner)] == [200, 200, 200, 200]
    assert [response.json() for response in (short, hidden, bot, owner)] == [
        {"qualified": False, "rewarded": False},
    ] * 4
    async with test_db["session_factory"]() as session:
        assert await session.scalar(select(func.count()).select_from(models.PublicShareVisit)) == 0
        assert (
            await session.scalar(
                select(func.count())
                .select_from(models.AcquisitionReward)
                .where(models.AcquisitionReward.reward_type == "social_share")
            )
            == 0
        )


@pytest.mark.asyncio
async def test_unique_qualified_session_rewards_owner_once_across_all_shares(
    client,
    test_db,
    job_factory,
    verified_user,
    auth_headers,
    monkeypatch,
):
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)
    initial_credits = verified_user.credits
    first_job = await _completed_job(test_db, job_factory, topic="Primeiro")
    second_job = await _completed_job(test_db, job_factory, topic="Segundo")
    first_token = (await _create_share(client, first_job.id, verified_user, auth_headers)).json()["token"]
    second_token = (await _create_share(client, second_job.id, verified_user, auth_headers)).json()["token"]
    session_id = uuid.uuid4()

    first = await client.post(
        f"/api/v1/public-shares/{first_token}/qualified-view",
        json=_view_payload(session_id),
        headers=_BROWSER_HEADERS,
    )
    replay = await client.post(
        f"/api/v1/public-shares/{first_token}/qualified-view",
        json=_view_payload(session_id),
        headers=_BROWSER_HEADERS,
    )
    other_share = await client.post(
        f"/api/v1/public-shares/{second_token}/qualified-view",
        json=_view_payload(),
        headers=_BROWSER_HEADERS,
    )

    assert first.status_code == replay.status_code == other_share.status_code == 200
    assert first.json() == {"qualified": True, "rewarded": True}
    assert replay.json() == {"qualified": False, "rewarded": False}
    assert other_share.json() == {"qualified": True, "rewarded": False}

    async with test_db["session_factory"]() as session:
        owner = await session.get(models.User, verified_user.id)
        rewards = list(
            await session.scalars(
                select(models.AcquisitionReward).where(
                    models.AcquisitionReward.user_id == verified_user.id,
                    models.AcquisitionReward.reward_type == "social_share",
                )
            )
        )
        visits = list(await session.scalars(select(models.PublicShareVisit)))
        events = list(await session.scalars(select(models.AnalyticsEvent.event_name)))
    assert owner is not None and owner.credits == initial_credits + 2
    assert [(reward.credits, reward.completed_job_id) for reward in rewards] == [(2, first_job.id)]
    assert len(visits) == 2
    assert all(visit.user_agent_classification == "browser" for visit in visits)
    assert "public_share_published" in events
    assert events.count("public_share_visited") == 2
    assert events.count("public_share_rewarded") == 1


@pytest.mark.asyncio
async def test_concurrent_first_views_are_unique_and_only_one_rewards(
    client,
    client_factory,
    test_db,
    job_factory,
    verified_user,
    auth_headers,
):
    initial_credits = verified_user.credits
    job = await _completed_job(test_db, job_factory)
    token = (await _create_share(client, job.id, verified_user, auth_headers)).json()["token"]

    async with client_factory("127.0.0.2") as first, client_factory("127.0.0.3") as second:
        responses = await asyncio.gather(
            first.post(
                f"/api/v1/public-shares/{token}/qualified-view",
                json=_view_payload(),
                headers=_BROWSER_HEADERS,
            ),
            second.post(
                f"/api/v1/public-shares/{token}/qualified-view",
                json=_view_payload(),
                headers=_BROWSER_HEADERS,
            ),
        )

    assert [response.status_code for response in responses] == [200, 200]
    assert [response.json()["qualified"] for response in responses] == [True, True]
    assert sorted(response.json()["rewarded"] for response in responses) == [False, True]
    async with test_db["session_factory"]() as session:
        owner = await session.get(models.User, verified_user.id)
        assert owner is not None and owner.credits == initial_credits + 2
        assert await session.scalar(select(func.count()).select_from(models.PublicShareVisit)) == 2
        assert (
            await session.scalar(
                select(func.count())
                .select_from(models.AcquisitionReward)
                .where(models.AcquisitionReward.reward_type == "social_share")
            )
            == 1
        )


@pytest.mark.asyncio
async def test_reward_analytics_failure_rolls_back_visit_reward_credit_and_ledger(
    client,
    test_db,
    job_factory,
    verified_user,
    auth_headers,
    monkeypatch,
):
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)
    job = await _completed_job(test_db, job_factory)
    token = (await _create_share(client, job.id, verified_user, auth_headers)).json()["token"]
    async with test_db["session_factory"]() as session:
        ledger_before = await session.scalar(select(func.count()).select_from(models.CreditLedgerEntry))
        await session.execute(
            text(
                """
                CREATE TRIGGER fail_public_share_rewarded
                BEFORE INSERT ON analytics_events
                WHEN NEW.event_name = 'public_share_rewarded'
                BEGIN SELECT RAISE(ABORT, 'share reward analytics unavailable'); END
                """
            )
        )
        await session.commit()

    response = await client.post(
        f"/api/v1/public-shares/{token}/qualified-view",
        json=_view_payload(),
        headers=_BROWSER_HEADERS,
    )
    assert response.status_code == 500

    async with test_db["session_factory"]() as session:
        owner = await session.get(models.User, verified_user.id)
        assert owner is not None and owner.credits == verified_user.credits
        assert await session.scalar(select(func.count()).select_from(models.PublicShareVisit)) == 0
        assert (
            await session.scalar(
                select(func.count())
                .select_from(models.AcquisitionReward)
                .where(models.AcquisitionReward.reward_type == "social_share")
            )
            == 0
        )
        assert await session.scalar(select(func.count()).select_from(models.CreditLedgerEntry)) == ledger_before


def test_public_share_tables_store_no_raw_ip_or_clear_token():
    assert "token" not in models.PublicVideoShare.__table__.columns
    assert "token_hash" in models.PublicVideoShare.__table__.columns
    assert all("ip" not in column.name.lower() for column in models.PublicShareVisit.__table__.columns)
    unique_sets = {
        tuple(column.name for column in constraint.columns)
        for constraint in models.PublicShareVisit.__table__.constraints
        if hasattr(constraint, "columns")
    }
    assert ("share_id", "anonymous_session_id") in unique_sets


@pytest.mark.asyncio
async def test_public_share_request_schema_is_strict(client):
    response = await client.post(
        "/api/v1/public-shares/not-a-token/qualified-view",
        json={**_view_payload(), "ip": "203.0.113.10"},
        headers=_BROWSER_HEADERS,
    )
    assert response.status_code == 422


_POSTGRES_ADMIN_DSN = os.getenv(
    "POSTGRES_PAYMENT_TEST_ADMIN_DSN",
    "postgresql://clipia:clipia_dev@localhost:5435/postgres",
)


def _require_postgres_tests() -> None:
    if os.getenv("RUN_POSTGRES_PAYMENT_TESTS") != "1":
        pytest.skip("set RUN_POSTGRES_PAYMENT_TESTS=1 to run real PostgreSQL public-share races")


def _postgres_database_urls(database_name: str) -> tuple[str, str]:
    admin_url = sa.engine.make_url(_POSTGRES_ADMIN_DSN)
    direct_url = admin_url.set(drivername="postgresql", database=database_name)
    async_url = admin_url.set(drivername="postgresql+asyncpg", database=database_name)
    return (
        async_url.render_as_string(hide_password=False),
        direct_url.render_as_string(hide_password=False),
    )


async def _create_postgres_database(database_name: str) -> None:
    connection = await asyncpg.connect(_POSTGRES_ADMIN_DSN)
    try:
        await connection.execute(f'CREATE DATABASE "{database_name}"')
    finally:
        await connection.close()


async def _drop_postgres_database(database_name: str) -> None:
    connection = await asyncpg.connect(_POSTGRES_ADMIN_DSN)
    try:
        await connection.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = $1 AND pid <> pg_backend_pid()",
            database_name,
        )
        await connection.execute(f'DROP DATABASE "{database_name}"')
    finally:
        await connection.close()


@pytest.fixture(scope="module")
def postgres_public_share_database():
    _require_postgres_tests()
    database_name = f"clipia_public_share_test_{uuid.uuid4().hex[:12]}"
    assert re.fullmatch(r"clipia_public_share_test_[0-9a-f]{12}", database_name)
    database_url, direct_dsn = _postgres_database_urls(database_name)
    previous = (settings.DATABASE_URL, settings.CREDIT_LEDGER_MODE, settings.ANALYTICS_ENABLED)

    asyncio.run(_create_postgres_database(database_name))
    try:
        settings.DATABASE_URL = database_url
        settings.CREDIT_LEDGER_MODE = "shadow"
        settings.ANALYTICS_ENABLED = True
        command.upgrade(Config("alembic.ini"), "head")
        yield {"database_url": database_url, "direct_dsn": direct_dsn}
    finally:
        settings.DATABASE_URL, settings.CREDIT_LEDGER_MODE, settings.ANALYTICS_ENABLED = previous
        asyncio.run(_drop_postgres_database(database_name))


def test_postgres_public_share_migration_is_head_and_hash_only(postgres_public_share_database):
    async def inspect_migration():
        connection = await asyncpg.connect(postgres_public_share_database["direct_dsn"])
        try:
            revision = await connection.fetchval("SELECT version_num FROM alembic_version")
            share_columns = {
                row["column_name"]
                for row in await connection.fetch(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = 'public_video_shares'"
                )
            }
            visit_columns = {
                row["column_name"]
                for row in await connection.fetch(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = 'public_share_visits'"
                )
            }
            active_index = await connection.fetchval(
                "SELECT indexdef FROM pg_indexes WHERE schemaname = 'public' "
                "AND indexname = 'uq_public_video_shares_active_job'"
            )
            return revision, share_columns, visit_columns, active_index
        finally:
            await connection.close()

    revision, share_columns, visit_columns, active_index = asyncio.run(inspect_migration())
    assert revision == "f9a0b1c2d3e4"
    assert "token_hash" in share_columns and "token" not in share_columns
    assert all("ip" not in column.lower() for column in visit_columns)
    assert "UNIQUE" in active_index and "WHERE (active = true)" in active_index


def test_postgres_concurrent_first_views_reward_and_ledger_once(postgres_public_share_database):
    async def run_race():
        engine = create_async_engine(
            postgres_public_share_database["database_url"],
            pool_size=5,
            max_overflow=5,
        )
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with sessions() as seed:
                owner = models.User(
                    email=f"public-share-{uuid.uuid4().hex}@example.com",
                    name="Public Share Owner",
                    password_hash="test",
                    credits=5,
                    plan="free",
                    email_verified=True,
                    referral_code=uuid.uuid4().hex[:8],
                )
                seed.add(owner)
                await seed.flush()
                job = models.Job(
                    user_id=owner.id,
                    topic="PostgreSQL public share",
                    style="educational",
                    duration_target=30,
                    status="completed",
                    video_url=f"/storage/output/{uuid.uuid4()}.mp4",
                    completed_at=datetime.now(timezone.utc),
                )
                seed.add(job)
                await seed.commit()
                owner_id, job_id = owner.id, job.id

            async with sessions() as publisher:
                persisted_owner = await publisher.get(models.User, owner_id)
                assert persisted_owner is not None
                published = await create_public_share(publisher, persisted_owner, job_id)
                token = published.token

            async def qualify(session_id: uuid.UUID):
                async with sessions() as session:
                    return await record_qualified_view(
                        session,
                        token=token,
                        anonymous_session_id=session_id,
                        dwell_ms=5000,
                        page_visible=True,
                        user_agent=_BROWSER_HEADERS["User-Agent"],
                        viewer_user_id=None,
                    )

            results = await asyncio.gather(qualify(uuid.uuid4()), qualify(uuid.uuid4()))
            async with sessions() as verification:
                persisted_owner = await verification.get(models.User, owner_id)
                rewards = list(
                    await verification.scalars(
                        select(models.AcquisitionReward).where(
                            models.AcquisitionReward.user_id == owner_id,
                            models.AcquisitionReward.reward_type == "social_share",
                        )
                    )
                )
                reward_ledger = list(
                    await verification.scalars(
                        select(models.CreditLedgerEntry).where(
                            models.CreditLedgerEntry.user_id == owner_id,
                            models.CreditLedgerEntry.origin == "social_share_reward",
                        )
                    )
                )
                visit_count = await verification.scalar(select(func.count()).select_from(models.PublicShareVisit))
                event_names = list(
                    await verification.scalars(
                        select(models.AnalyticsEvent.event_name).where(
                            models.AnalyticsEvent.event_name.in_(("public_share_visited", "public_share_rewarded"))
                        )
                    )
                )
            return results, persisted_owner, rewards, reward_ledger, visit_count, event_names, job_id
        finally:
            await engine.dispose()

    results, owner, rewards, reward_ledger, visit_count, event_names, job_id = asyncio.run(run_race())
    assert sorted(results) == [(True, False), (True, True)]
    assert owner is not None and owner.credits == 7
    assert [(reward.credits, reward.completed_job_id) for reward in rewards] == [(2, job_id)]
    assert [(entry.delta, entry.origin, entry.balance_after) for entry in reward_ledger] == [
        (2, "social_share_reward", 7)
    ]
    assert visit_count == 2
    assert event_names.count("public_share_visited") == 2
    assert event_names.count("public_share_rewarded") == 1
