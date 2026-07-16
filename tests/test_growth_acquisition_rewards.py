import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from pydantic import ValidationError
from sqlalchemy import CheckConstraint, Index, UniqueConstraint, func, select

from app.analytics.schemas import CreditBalanceChangedProperties
from app.auth.schemas import RegisterRequest
from app.db import models
from app.services import job_operations


async def _seed_offer(db_session, *, active: bool = True, expires_at: datetime | None = None):
    offer = models.MarketingOffer(
        code="creator20_v1",
        bonus_credits=18,
        is_active=active,
        expires_at=expires_at,
    )
    db_session.add(offer)
    await db_session.commit()
    return offer


async def _register(client, email: str, **extra):
    return await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "name": "Growth Creator",
            "password": "Secret123",
            "consent": True,
            **extra,
        },
    )


def test_registration_schema_captures_offer_and_optional_marketing_measurement_consent():
    campaign = RegisterRequest.model_validate(
        {
            "email": "creator@example.com",
            "name": "Creator",
            "password": "Secret123",
            "consent": True,
            "offer_code": " CREATOR20_V1 ",
            "marketing_measurement_consent": True,
        }
    )
    direct = RegisterRequest.model_validate(
        {
            "email": "direct@example.com",
            "name": "Direct",
            "password": "Secret123",
            "consent": True,
        }
    )

    assert campaign.offer_code == "creator20_v1"
    assert campaign.marketing_measurement_consent is True
    assert direct.offer_code is None
    assert direct.marketing_measurement_consent is False


def test_acquisition_reward_models_enforce_offer_and_exclusivity_contracts():
    assert hasattr(models, "MarketingOffer")
    assert hasattr(models, "AcquisitionReward")

    offer_columns = models.MarketingOffer.__table__.columns
    assert {"id", "code", "bonus_credits", "is_active", "expires_at", "created_at"}.issubset(offer_columns.keys())
    assert offer_columns.code.unique is True

    reward_table = models.AcquisitionReward.__table__
    constraints = reward_table.constraints
    assert any(
        isinstance(constraint, UniqueConstraint)
        and {column.name for column in constraint.columns} == {"user_id", "reward_type"}
        for constraint in constraints
    )
    reward_type_checks = [
        str(constraint.sqltext)
        for constraint in constraints
        if isinstance(constraint, CheckConstraint) and "reward_type" in str(constraint.sqltext)
    ]
    assert reward_type_checks and all(
        reward_type in reward_type_checks[0]
        for reward_type in ("campaign_signup", "referral_activation", "social_share")
    )
    assert any(
        isinstance(index, Index) and index.unique and [column.name for column in index.columns] == ["user_id"]
        for index in reward_table.indexes
    )

    user_columns = models.User.__table__.columns
    assert {"acquisition_offer_id", "marketing_measurement_consented_at"}.issubset(user_columns.keys())


def test_growth_reward_migration_seeds_real_offer_and_enforces_exclusivity(monkeypatch):
    migration_path = Path("alembic/versions/e8f9a0b1c2d3_add_growth_acquisition_rewards.py")
    assert migration_path.exists()
    spec = spec_from_file_location("growth_acquisition_rewards", migration_path)
    assert spec and spec.loader
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.revision == "e8f9a0b1c2d3"
    assert migration.down_revision == "d7e8f9a0b1c2"

    engine = sa.create_engine("sqlite:///:memory:")
    user_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(sa.text("PRAGMA foreign_keys=ON"))
        connection.execute(sa.text("CREATE TABLE users (id CHAR(32) PRIMARY KEY)"))
        connection.execute(sa.text("CREATE TABLE jobs (id CHAR(32) PRIMARY KEY)"))
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))

        migration.upgrade()

        inspector = sa.inspect(connection)
        assert {"marketing_offers", "acquisition_rewards"}.issubset(inspector.get_table_names())
        assert {"acquisition_offer_id", "marketing_measurement_consented_at"}.issubset(
            {column["name"] for column in inspector.get_columns("users")}
        )
        offer = (
            connection.execute(
                sa.text(
                    "SELECT id, bonus_credits, is_active, expires_at FROM marketing_offers "
                    "WHERE code = 'creator20_v1'"
                )
            )
            .mappings()
            .one()
        )
        assert offer["bonus_credits"] == 18
        assert bool(offer["is_active"]) is True
        assert offer["expires_at"] is None

        connection.execute(sa.text("INSERT INTO users (id) VALUES (:id)"), {"id": user_id.hex})
        connection.execute(
            sa.text(
                "INSERT INTO acquisition_rewards "
                "(id, user_id, reward_type, credits, marketing_offer_id, occurred_at) "
                "VALUES (:id, :user_id, 'campaign_signup', 18, :offer_id, CURRENT_TIMESTAMP)"
            ),
            {"id": uuid.uuid4().hex, "user_id": user_id.hex, "offer_id": offer["id"]},
        )
        with pytest.raises(sa.exc.IntegrityError):
            connection.execute(
                sa.text(
                    "INSERT INTO acquisition_rewards "
                    "(id, user_id, reward_type, credits, occurred_at) "
                    "VALUES (:id, :user_id, 'referral_activation', 18, CURRENT_TIMESTAMP)"
                ),
                {"id": uuid.uuid4().hex, "user_id": user_id.hex},
            )
        connection.execute(
            sa.text(
                "INSERT INTO acquisition_rewards "
                "(id, user_id, reward_type, credits, occurred_at) "
                "VALUES (:id, :user_id, 'social_share', 2, CURRENT_TIMESTAMP)"
            ),
            {"id": uuid.uuid4().hex, "user_id": user_id.hex},
        )

        migration.downgrade()
        inspector = sa.inspect(connection)
        assert "marketing_offers" not in inspector.get_table_names()
        assert "acquisition_rewards" not in inspector.get_table_names()
        assert "acquisition_offer_id" not in {column["name"] for column in inspector.get_columns("users")}


@pytest.mark.asyncio
async def test_direct_and_invalid_or_inactive_offer_verification_grant_only_two_credits(client, db_session):
    await _seed_offer(db_session, active=False)
    cases = (
        ("direct-growth@example.com", {}),
        ("invalid-offer@example.com", {"offer_code": "missing_offer"}),
        ("inactive-offer@example.com", {"offer_code": "creator20_v1"}),
    )

    for email, extra in cases:
        registered = await _register(client, email, **extra)
        assert registered.status_code == 201
        user = await db_session.scalar(select(models.User).where(models.User.email == email))
        assert user is not None and user.verification_code
        verified = await client.post(
            "/api/v1/auth/verify-email",
            json={"email": email, "code": user.verification_code},
        )
        assert verified.status_code == 200
        assert verified.json() == {"status": "verified", "credits": 2}

    db_session.expire_all()
    balances = list(
        await db_session.scalars(
            select(models.User.credits).where(models.User.email.in_([email for email, _extra in cases]))
        )
    )
    assert balances == [2, 2, 2]
    assert await db_session.scalar(select(func.count()).select_from(models.AcquisitionReward)) == 0


@pytest.mark.asyncio
async def test_creator_offer_verification_adds_base_then_campaign_reward_once(client, db_session, monkeypatch):
    monkeypatch.setattr("app.auth.routes.settings.WELCOME_CREDIT_BONUS", 2)
    offer = await _seed_offer(db_session)
    registered = await _register(
        client,
        "campaign-growth@example.com",
        offer_code="creator20_v1",
        marketing_measurement_consent=True,
    )
    assert registered.status_code == 201
    user = await db_session.scalar(select(models.User).where(models.User.email == "campaign-growth@example.com"))
    assert user is not None and user.verification_code
    user_id = user.id
    assert user.acquisition_offer_id == offer.id
    assert user.marketing_measurement_consented_at is not None

    verified = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": user.email, "code": user.verification_code},
    )
    replay = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": user.email, "code": user.verification_code},
    )

    assert verified.status_code == 200
    assert verified.json() == {"status": "verified", "credits": 20}
    assert replay.json() == {"status": "already_verified"}
    db_session.expire_all()
    persisted = await db_session.get(models.User, user_id)
    assert persisted is not None and persisted.credits == 20
    rewards = list(
        await db_session.scalars(select(models.AcquisitionReward).where(models.AcquisitionReward.user_id == user_id))
    )
    assert [(reward.reward_type, reward.credits) for reward in rewards] == [("campaign_signup", 18)]


@pytest.mark.asyncio
async def test_campaign_registration_ignores_simultaneous_referral_code(
    client,
    db_session,
    verified_user,
):
    offer = await _seed_offer(db_session)
    response = await _register(
        client,
        "campaign-with-referral@example.com",
        offer_code=offer.code,
        referral_code=verified_user.referral_code,
    )

    assert response.status_code == 201
    user = await db_session.scalar(select(models.User).where(models.User.email == "campaign-with-referral@example.com"))
    assert user is not None
    assert user.acquisition_offer_id == offer.id
    assert user.referred_by is None


@pytest.mark.asyncio
async def test_concurrent_campaign_verification_never_duplicates_reward(
    client,
    client_factory,
    db_session,
):
    await _seed_offer(db_session)
    registered = await _register(client, "campaign-concurrent@example.com", offer_code="creator20_v1")
    assert registered.status_code == 201
    user = await db_session.scalar(select(models.User).where(models.User.email == "campaign-concurrent@example.com"))
    assert user is not None and user.verification_code
    user_id = user.id
    payload = {"email": user.email, "code": user.verification_code}

    async with client_factory("127.0.0.2") as first, client_factory("127.0.0.3") as second:
        responses = await asyncio.gather(
            first.post("/api/v1/auth/verify-email", json=payload),
            second.post("/api/v1/auth/verify-email", json=payload),
        )

    assert [response.status_code for response in responses] == [200, 200]
    assert sorted(response.json()["status"] for response in responses) == ["already_verified", "verified"]
    db_session.expire_all()
    persisted = await db_session.get(models.User, user_id)
    assert persisted is not None and persisted.credits == 20
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(models.AcquisitionReward)
            .where(models.AcquisitionReward.user_id == user_id)
        )
        == 1
    )


@pytest.mark.asyncio
async def test_referral_verification_does_not_reward_until_first_generation_finishes(
    client,
    db_session,
    verified_user,
):
    referrer_id = verified_user.id
    initial_balance = verified_user.credits
    registered = await _register(
        client,
        "activated-referral@example.com",
        referral_code=verified_user.referral_code,
    )
    assert registered.status_code == 201
    referred = await db_session.scalar(select(models.User).where(models.User.email == "activated-referral@example.com"))
    assert referred is not None and referred.verification_code
    referred_id = referred.id
    verified = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": referred.email, "code": referred.verification_code},
    )
    assert verified.status_code == 200

    db_session.expire_all()
    assert (await db_session.get(models.User, referrer_id)).credits == initial_balance
    assert await db_session.scalar(select(func.count()).select_from(models.ReferralCreditAward)) == 0

    completed_job = models.Job(
        user_id=referred_id,
        topic="Primeira geração ativada",
        style="educational",
        duration_target=30,
        status="finalizing",
    )
    db_session.add(completed_job)
    await db_session.commit()
    result = await job_operations.finalize_generation(
        db_session,
        completed_job.id,
        script={"scenes": []},
        video_url=f"/storage/output/{completed_job.id}.mp4",
        telemetry={},
    )
    await db_session.commit()
    replay = await job_operations.finalize_generation(
        db_session,
        completed_job.id,
        script={"scenes": []},
        video_url=f"/storage/output/{completed_job.id}.mp4",
        telemetry={},
    )
    await db_session.commit()

    assert result == "finalized"
    assert replay == "ignored"
    db_session.expire_all()
    assert (await db_session.get(models.User, referrer_id)).credits == initial_balance + 18
    rewards = list(
        await db_session.scalars(
            select(models.AcquisitionReward).where(models.AcquisitionReward.user_id == referrer_id)
        )
    )
    assert [(reward.reward_type, reward.credits, reward.source_user_id) for reward in rewards] == [
        ("referral_activation", 18, referred_id)
    ]
    assert await db_session.scalar(select(func.count()).select_from(models.ReferralCreditAward)) == 0


@pytest.mark.asyncio
async def test_campaign_reward_recipient_cannot_also_claim_referral_activation(
    client,
    db_session,
):
    await _seed_offer(db_session)
    assert (await _register(client, "exclusive-campaign@example.com", offer_code="creator20_v1")).status_code == 201
    campaign_user = await db_session.scalar(
        select(models.User).where(models.User.email == "exclusive-campaign@example.com")
    )
    assert campaign_user is not None and campaign_user.verification_code
    campaign_user_id = campaign_user.id
    campaign_referral_code = campaign_user.referral_code
    assert (
        await client.post(
            "/api/v1/auth/verify-email",
            json={"email": campaign_user.email, "code": campaign_user.verification_code},
        )
    ).json()["credits"] == 20

    assert (
        await _register(
            client,
            "exclusive-referred@example.com",
            referral_code=campaign_referral_code,
        )
    ).status_code == 201
    referred = await db_session.scalar(select(models.User).where(models.User.email == "exclusive-referred@example.com"))
    assert referred is not None and referred.verification_code
    referred_id = referred.id
    assert (
        await client.post(
            "/api/v1/auth/verify-email",
            json={"email": referred.email, "code": referred.verification_code},
        )
    ).status_code == 200

    job = models.Job(
        user_id=referred_id,
        topic="Exclusividade de aquisição",
        style="educational",
        duration_target=30,
        status="finalizing",
    )
    db_session.add(job)
    await db_session.commit()
    assert (
        await job_operations.finalize_generation(
            db_session,
            job.id,
            script={},
            video_url=f"/storage/output/{job.id}.mp4",
            telemetry={},
        )
        == "finalized"
    )
    await db_session.commit()

    db_session.expire_all()
    assert (await db_session.get(models.User, campaign_user_id)).credits == 20
    rewards = list(
        await db_session.scalars(
            select(models.AcquisitionReward).where(models.AcquisitionReward.user_id == campaign_user_id)
        )
    )
    assert [(reward.reward_type, reward.credits) for reward in rewards] == [("campaign_signup", 18)]


def test_credit_analytics_accepts_only_new_catalogued_reasons_and_strict_properties():
    assert (
        CreditBalanceChangedProperties.model_validate({"reason": "campaign_signup", "delta": 18}).reason
        == "campaign_signup"
    )
    assert (
        CreditBalanceChangedProperties.model_validate({"reason": "referral_activation", "delta": 18}).reason
        == "referral_activation"
    )
    with pytest.raises(ValidationError):
        CreditBalanceChangedProperties.model_validate(
            {"reason": "campaign_signup", "delta": 18, "email": "leak@example.com"}
        )
    with pytest.raises(ValidationError):
        CreditBalanceChangedProperties.model_validate({"reason": "invented_reward", "delta": 18})


@pytest.mark.asyncio
async def test_later_generation_is_ineligible_but_generation_ordinal_first_can_claim(
    db_session,
    verified_user,
):
    referrer_id = verified_user.id
    referred = models.User(
        email="ordinal-referral@example.com",
        name="Ordinal Referral",
        password_hash="hashed",
        credits=2,
        email_verified=True,
        referred_by=verified_user.id,
    )
    db_session.add(referred)
    await db_session.flush()
    now = datetime.now(timezone.utc)
    first = models.Job(
        user_id=referred.id,
        topic="Primeira criada",
        style="educational",
        duration_target=30,
        status="finalizing",
        created_at=now - timedelta(minutes=1),
    )
    later = models.Job(
        user_id=referred.id,
        topic="Segunda criada",
        style="educational",
        duration_target=30,
        status="finalizing",
        created_at=now,
    )
    db_session.add_all([first, later])
    await db_session.commit()
    first_id = first.id
    later_id = later.id
    initial_balance = verified_user.credits

    assert (
        await job_operations.finalize_generation(
            db_session,
            later_id,
            script={},
            video_url=f"/storage/output/{later_id}.mp4",
            telemetry={},
        )
        == "finalized"
    )
    await db_session.commit()
    db_session.expire_all()
    assert (await db_session.get(models.User, referrer_id)).credits == initial_balance

    assert (
        await job_operations.finalize_generation(
            db_session,
            first_id,
            script={},
            video_url=f"/storage/output/{first_id}.mp4",
            telemetry={},
        )
        == "finalized"
    )
    await db_session.commit()
    db_session.expire_all()
    assert (await db_session.get(models.User, referrer_id)).credits == initial_balance + 18
