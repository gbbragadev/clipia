import asyncio
import hashlib
import importlib.util
import json
import logging
import os
import re
import socket
import uuid
from datetime import datetime, timezone
from pathlib import Path

import asyncpg
import pytest
import sqlalchemy as sa
import uvicorn
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.analytics.schemas import SERVER_EVENT_PROPERTY_MODELS
from app.analytics.service import append_server_event
from app.auth.service import create_access_token
from app.auth.session import AUTH_COOKIE_NAME
from app.config import settings
from app.db import models
from app.public_shares.service import create_public_share, record_qualified_view
from app.services.job_operations import finalize_generation
from tests.migration_contract import EXPECTED_ALEMBIC_HEAD

_BROWSER_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0"}
_REPO_ROOT = Path(__file__).resolve().parents[1]
_DIRECT_UVICORN_LAUNCHERS = (
    "Dockerfile",
    "scripts/start-all.ps1",
    "scripts/install-windows-services.ps1",
    "scripts/_run-backend.ps1",
)


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


@pytest.mark.asyncio
async def test_finalized_editable_video_can_be_shared_and_rewarded(
    client,
    db_session,
    test_db,
    verified_user,
    auth_headers,
):
    """Exercise the delivered state emitted by the real generation finalizer."""
    initial_balance = verified_user.credits
    job = models.Job(
        user_id=verified_user.id,
        topic="Entrega editavel real",
        style="educational",
        duration_target=30,
        status="finalizing",
    )
    db_session.add(job)
    await db_session.commit()
    result = await finalize_generation(
        db_session,
        job.id,
        script={"scenes": []},
        video_url=f"/storage/output/{job.id}.mp4",
        telemetry={},
    )
    await db_session.commit()
    await db_session.refresh(job)
    assert result == "finalized"
    assert job.status == "editable"

    output_dir = test_db["storage_dir"] / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"{job.id}.mp4").write_bytes(b"finalized-editable-video")

    created = await _create_share(client, job.id, verified_user, auth_headers)
    assert created.status_code == 200
    token = created.json()["token"]
    qualified = await client.post(
        f"/api/v1/public-shares/{token}/qualified-view",
        json=_view_payload(),
        headers=_BROWSER_HEADERS,
    )
    assert qualified.status_code == 200
    assert qualified.json() == {"qualified": True, "rewarded": True}

    db_session.expire_all()
    owner = await db_session.get(models.User, verified_user.id)
    assert owner is not None and owner.credits == initial_balance + 2


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
async def test_public_share_requires_owned_delivered_video_and_is_idempotent(
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
    hostile_topic = "owner@example.com C:\\private\\customer\\raw-output.mp4 secret-token"
    job = await _completed_job(test_db, job_factory, topic=hostile_topic)
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
    assert payload["title"] == "Vídeo publicado com ClipIA"
    assert payload["active"] is True
    assert datetime.fromisoformat(payload["published_at"]).tzinfo is not None
    assert payload["video_url"].endswith(f"/api/v1/public-shares/{token}/video")
    serialized = str(payload).lower()
    for forbidden in ("owner@example.com", "storage", "private", "raw-output", "secret-token"):
        assert forbidden not in serialized

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
    default_user_agent = client.headers.get("User-Agent")
    if default_user_agent is not None:
        del client.headers["User-Agent"]
    try:
        absent_user_agent = await client.post(
            f"/api/v1/public-shares/{token}/qualified-view",
            json=_view_payload(),
        )
    finally:
        if default_user_agent is not None:
            client.headers["User-Agent"] = default_user_agent
    empty_user_agent = await client.post(
        f"/api/v1/public-shares/{token}/qualified-view",
        json=_view_payload(),
        headers={"User-Agent": ""},
    )
    unknown_user_agent = await client.post(
        f"/api/v1/public-shares/{token}/qualified-view",
        json=_view_payload(),
        headers={"User-Agent": "custom-agent/1.0"},
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

    rejected = (short, hidden, absent_user_agent, empty_user_agent, unknown_user_agent, bot, owner)
    assert [response.status_code for response in rejected] == [200] * len(rejected)
    assert [response.json() for response in rejected] == [
        {"qualified": False, "rewarded": False},
    ] * len(rejected)
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
async def test_valid_owner_cookie_beats_invalid_bearer_but_invalid_bearer_alone_is_anonymous(
    client,
    test_db,
    job_factory,
    verified_user,
    auth_headers,
):
    job = await _completed_job(test_db, job_factory)
    token = (await _create_share(client, job.id, verified_user, auth_headers)).json()["token"]
    client.cookies.set(AUTH_COOKIE_NAME, create_access_token(str(verified_user.id)))

    owner = await client.post(
        f"/api/v1/public-shares/{token}/qualified-view",
        json=_view_payload(),
        headers={**_BROWSER_HEADERS, "Authorization": "Bearer invalid-token"},
    )
    client.cookies.clear()
    anonymous = await client.post(
        f"/api/v1/public-shares/{token}/qualified-view",
        json=_view_payload(),
        headers={**_BROWSER_HEADERS, "Authorization": "Bearer invalid-token"},
    )

    assert owner.status_code == anonymous.status_code == 200
    assert owner.json() == {"qualified": False, "rewarded": False}
    assert anonymous.json() == {"qualified": True, "rewarded": True}


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
        reward_ledger = list(
            await session.scalars(
                select(models.CreditLedgerEntry).where(
                    models.CreditLedgerEntry.user_id == verified_user.id,
                    models.CreditLedgerEntry.delta == 2,
                )
            )
        )
    assert owner is not None and owner.credits == initial_credits + 2
    assert [(reward.credits, reward.completed_job_id) for reward in rewards] == [(2, first_job.id)]
    assert len(visits) == 2
    assert all(visit.user_agent_classification == "browser" for visit in visits)
    assert len(reward_ledger) == 1
    assert reward_ledger[0].origin == "social_share_reward"
    assert reward_ledger[0].idempotency_key == f"acquisition:{verified_user.id}:social_share"
    assert reward_ledger[0].operation_id == rewards[0].id
    assert reward_ledger[0].job_id == first_job.id
    assert reward_ledger[0].balance_after == initial_credits + 2
    assert "share_page_published" in events
    assert events.count("share_page_visited") == 2
    assert events.count("social_share_rewarded") == 1


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
                WHEN NEW.event_name = 'social_share_rewarded'
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


@pytest.mark.asyncio
async def test_public_share_access_logs_redact_capability_and_omit_raw_ip(
    client,
    client_factory,
    test_db,
    job_factory,
    verified_user,
    auth_headers,
    caplog,
):
    job = await _completed_job(test_db, job_factory)
    token = (await _create_share(client, job.id, verified_user, auth_headers)).json()["token"]
    caplog.clear()

    with caplog.at_level(logging.INFO, logger="clipia.access"):
        async with client_factory("203.0.113.77") as public_client:
            assert (await public_client.get(f"/api/v1/public-shares/{token}")).status_code == 200
            assert (
                await public_client.post(
                    f"/api/v1/public-shares/{token}/qualified-view",
                    json=_view_payload(),
                    headers={"User-Agent": ""},
                )
            ).status_code == 200
            assert (await public_client.get("/api/v1/config")).status_code == 200

    payloads = [json.loads(record.message) for record in caplog.records if record.name == "clipia.access"]
    public_payloads = [payload for payload in payloads if payload["path"].startswith("/api/v1/public-shares/")]
    assert {payload["path"] for payload in public_payloads} == {
        "/api/v1/public-shares/[redacted]",
        "/api/v1/public-shares/[redacted]/qualified-view",
    }
    assert all("client_ip" not in payload and "remote_addr" not in payload for payload in public_payloads)
    public_logs = "\n".join(json.dumps(payload, sort_keys=True) for payload in public_payloads)
    assert token not in public_logs
    assert "203.0.113.77" not in public_logs

    normal_payload = next(payload for payload in payloads if payload["path"] == "/api/v1/config")
    assert normal_payload["client_ip"] == "203.0.113.77"


def test_controlled_uvicorn_launcher_inventory_disables_builtin_access_log():
    for relative_path in _DIRECT_UVICORN_LAUNCHERS:
        source = (_REPO_ROOT / relative_path).read_text(encoding="utf-8")
        commands = [
            line for line in source.splitlines() if re.search(r"\buvicorn\b.*\bapp\.main:app\b", line, re.IGNORECASE)
        ]
        assert commands, f"missing inventoried Uvicorn command in {relative_path}"
        assert all("--no-access-log" in command for command in commands), relative_path

    delegates = {
        "docker-compose.yml": "build: .",
        "scripts/start-production.ps1": "_run-backend.ps1",
        "scripts/restart-backend-only.ps1": "_run-backend.ps1",
    }
    for relative_path, expected_delegate in delegates.items():
        source = (_REPO_ROOT / relative_path).read_text(encoding="utf-8")
        assert expected_delegate in source


@pytest.mark.asyncio
async def test_configured_uvicorn_server_emits_only_redacted_middleware_access_log(app, caplog):
    launcher = (_REPO_ROOT / "scripts/_run-backend.ps1").read_text(encoding="utf-8")
    access_log_enabled = "--no-access-log" not in launcher
    capability = "sensitive-public-share-capability-token"
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(128)
    port = sock.getsockname()[1]
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        access_log=access_log_enabled,
        lifespan="off",
        log_config=None,
    )
    server = uvicorn.Server(config)

    caplog.clear()
    with caplog.at_level(logging.INFO):
        server_task = asyncio.create_task(server.serve(sockets=[sock]))
        try:
            for _ in range(200):
                if server.started:
                    break
                await asyncio.sleep(0.01)
            assert server.started
            async with AsyncClient(base_url=f"http://127.0.0.1:{port}") as network_client:
                response = await network_client.get(f"/api/v1/public-shares/{capability}")
            assert response.status_code == 404
        finally:
            server.should_exit = True
            await asyncio.wait_for(server_task, timeout=5)
            sock.close()

    uvicorn_access = [record.getMessage() for record in caplog.records if record.name == "uvicorn.access"]
    middleware_access = [record.getMessage() for record in caplog.records if record.name == "clipia.access"]
    assert uvicorn_access == []
    assert any("/api/v1/public-shares/[redacted]" in message for message in middleware_access)
    assert capability not in "\n".join(middleware_access)


@pytest.mark.asyncio
async def test_share_server_analytics_reject_arbitrary_properties(db_session, verified_user, monkeypatch):
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)
    with pytest.raises(ValidationError):
        await append_server_event(
            db_session,
            event_name="share_page_published",
            user=verified_user,
            properties={
                "share_id": str(uuid.uuid4()),
                "job_id": str(uuid.uuid4()),
                "raw_payload": "not allowed",
            },
            idempotency_key=f"strict-share:{uuid.uuid4()}",
            occurred_at=datetime.now(timezone.utc),
        )


def test_share_server_analytics_catalog_is_strict_and_complete():
    assert {
        "share_page_published",
        "share_page_visited",
        "social_share_rewarded",
    }.issubset(SERVER_EVENT_PROPERTY_MODELS)
    published = SERVER_EVENT_PROPERTY_MODELS["share_page_published"].model_validate(
        {"share_id": str(uuid.uuid4()), "job_id": str(uuid.uuid4())}
    )
    assert published.model_dump(mode="json").keys() == {"share_id", "job_id"}
    with pytest.raises(ValidationError):
        SERVER_EVENT_PROPERTY_MODELS["social_share_rewarded"].model_validate(
            {
                "share_id": str(uuid.uuid4()),
                "job_id": str(uuid.uuid4()),
                "credits": 2,
                "email": "leak@example.com",
            }
        )


def _load_public_share_migration():
    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / ("f9a0b1c2d3e4_add_public_video_shares.py")
    spec = importlib.util.spec_from_file_location("task2_public_share_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sqlite_f9_upgrade_and_downgrade_enforce_share_uniqueness():
    migration = _load_public_share_migration()
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    users = sa.Table(
        "users",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("credits", sa.Integer(), nullable=False, server_default="5"),
    )
    jobs = sa.Table(
        "jobs",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey(users.c.id), nullable=False),
    )
    credit_ledger_entries = sa.Table(
        "credit_ledger_entries",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey(users.c.id), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("origin", sa.String(50), nullable=False),
        sa.Column("purchase_id", sa.Uuid()),
        sa.Column("job_id", sa.Uuid()),
        sa.Column("operation_id", sa.Uuid()),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False, unique=True),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    sa.Table(
        "analytics_events",
        metadata,
        sa.Column("event_name", sa.String(50), nullable=False),
        sa.CheckConstraint(migration._ANALYTICS_EVENTS_BEFORE, name="ck_analytics_event_name"),
    )
    metadata.create_all(engine)

    owner_id, job_id = uuid.uuid4(), uuid.uuid4()
    share_id, other_share_id = uuid.uuid4(), uuid.uuid4()
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TRIGGER credit_ledger_users_update
            AFTER UPDATE OF credits ON users
            WHEN NEW.credits <> OLD.credits
            BEGIN
                INSERT INTO credit_ledger_entries (
                    id, user_id, delta, origin, reason, idempotency_key,
                    balance_after, created_at
                ) VALUES (
                    lower(hex(randomblob(16))), NEW.id, NEW.credits - OLD.credits,
                    'unclassified', 'legacy trigger',
                    'shadow:' || lower(hex(randomblob(16))), NEW.credits, CURRENT_TIMESTAMP
                );
            END
            """
        )
        operations = Operations(MigrationContext.configure(connection))
        migration.op = operations
        migration.upgrade()

        inspector = sa.inspect(connection)
        assert {"public_video_shares", "public_share_visits"}.issubset(inspector.get_table_names())
        analytics_check = next(
            check["sqltext"]
            for check in inspector.get_check_constraints("analytics_events")
            if check["name"] == "ck_analytics_event_name"
        )
        assert "share_page_published" in analytics_check
        assert "share_page_visited" in analytics_check
        assert "social_share_rewarded" in analytics_check
        assert "public_share_published" not in analytics_check
        contextual_trigger = connection.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type = 'trigger' AND name = 'credit_ledger_users_update'"
        ).scalar_one()
        assert "clipia_get_credit_context" in contextual_trigger

        connection.execute(users.insert().values(id=owner_id))
        connection.execute(jobs.insert().values(id=job_id, user_id=owner_id))
        operation_id = uuid.uuid4()
        idempotency_key = f"acquisition:{owner_id}:social_share"
        connection.exec_driver_sql(
            "SELECT clipia_set_credit_context(?, ?, ?, ?, ?, ?)",
            (
                "social_share_reward",
                "social_share acquisition reward",
                idempotency_key,
                None,
                str(job_id),
                str(operation_id),
            ),
        )
        connection.execute(users.update().where(users.c.id == owner_id).values(credits=7))
        ledger_row = connection.execute(sa.select(credit_ledger_entries)).mappings().one()
        assert ledger_row["delta"] == 2
        assert ledger_row["origin"] == "social_share_reward"
        assert ledger_row["idempotency_key"] == idempotency_key
        assert ledger_row["job_id"] == job_id
        assert ledger_row["operation_id"] == operation_id
        assert ledger_row["balance_after"] == 7
        shares = sa.table(
            "public_video_shares",
            sa.column("id", sa.Uuid()),
            sa.column("job_id", sa.Uuid()),
            sa.column("owner_id", sa.Uuid()),
            sa.column("token_hash", sa.String()),
            sa.column("active", sa.Boolean()),
            sa.column("revoked_at", sa.DateTime(timezone=True)),
        )
        connection.execute(
            shares.insert().values(
                id=share_id,
                job_id=job_id,
                owner_id=owner_id,
                token_hash="a" * 64,
                active=True,
            )
        )
        with pytest.raises(sa.exc.IntegrityError), connection.begin_nested():
            connection.execute(
                shares.insert().values(
                    id=other_share_id,
                    job_id=job_id,
                    owner_id=owner_id,
                    token_hash="b" * 64,
                    active=True,
                )
            )
        connection.execute(
            shares.insert().values(
                id=other_share_id,
                job_id=job_id,
                owner_id=owner_id,
                token_hash="b" * 64,
                active=False,
                revoked_at=datetime.now(timezone.utc),
            )
        )

        visits = sa.table(
            "public_share_visits",
            sa.column("id", sa.Uuid()),
            sa.column("share_id", sa.Uuid()),
            sa.column("anonymous_session_id", sa.Uuid()),
            sa.column("user_agent_classification", sa.String()),
        )
        anonymous_session_id = uuid.uuid4()
        connection.execute(
            visits.insert().values(
                id=uuid.uuid4(),
                share_id=share_id,
                anonymous_session_id=anonymous_session_id,
                user_agent_classification="browser",
            )
        )
        with pytest.raises(sa.exc.IntegrityError), connection.begin_nested():
            connection.execute(
                visits.insert().values(
                    id=uuid.uuid4(),
                    share_id=share_id,
                    anonymous_session_id=anonymous_session_id,
                    user_agent_classification="browser",
                )
            )

        migration.downgrade()
        assert "public_video_shares" not in sa.inspect(connection).get_table_names()
        assert "public_share_visits" not in sa.inspect(connection).get_table_names()
        downgraded_trigger = connection.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type = 'trigger' AND name = 'credit_ledger_users_update'"
        ).scalar_one()
        assert "clipia_get_credit_context" not in downgraded_trigger
        assert "unclassified" in downgraded_trigger


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
    assert revision == EXPECTED_ALEMBIC_HEAD
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
                        viewer_user_ids=frozenset(),
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
                            models.AnalyticsEvent.event_name.in_(("share_page_visited", "social_share_rewarded"))
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
    assert event_names.count("share_page_visited") == 2
    assert event_names.count("social_share_rewarded") == 1
