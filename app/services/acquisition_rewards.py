from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.service import append_server_event
from app.db.models import AcquisitionReward, Job, MarketingOffer, User
from app.services.credit_ledger import set_credit_ledger_context

CAMPAIGN_REWARD_TYPE = "campaign_signup"
CAMPAIGN_OFFER_CODE = "creator20_v1"
CAMPAIGN_REWARD_CREDITS = 18
REFERRAL_REWARD_TYPE = "referral_activation"
REFERRAL_ACTIVATION_CREDITS = 18
SOCIAL_SHARE_REWARD_TYPE = "social_share"
SOCIAL_SHARE_REWARD_CREDITS = 2
_ACQUISITION_REWARD_TYPES = (CAMPAIGN_REWARD_TYPE, REFERRAL_REWARD_TYPE)


async def _lock_reward_recipient(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await db.scalar(
        select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True)
    )


async def _already_has_acquisition_reward(db: AsyncSession, user_id: uuid.UUID) -> bool:
    reward_id = await db.scalar(
        select(AcquisitionReward.id).where(
            AcquisitionReward.user_id == user_id,
            AcquisitionReward.reward_type.in_(_ACQUISITION_REWARD_TYPES),
        )
    )
    return reward_id is not None


async def _credit_reward(
    db: AsyncSession,
    *,
    recipient: User,
    reward: AcquisitionReward,
    reason: str,
    origin: str,
    occurred_at: datetime,
) -> int:
    db.add(reward)
    await db.flush()
    return await _apply_reward_credit(
        db,
        recipient=recipient,
        reward=reward,
        reason=reason,
        origin=origin,
        occurred_at=occurred_at,
    )


async def _apply_reward_credit(
    db: AsyncSession,
    *,
    recipient: User,
    reward: AcquisitionReward,
    reason: str,
    origin: str,
    occurred_at: datetime,
) -> int:
    idempotency_key = f"acquisition:{recipient.id}:{reward.reward_type}"
    await set_credit_ledger_context(
        db,
        origin=origin,
        reason=f"{reason} acquisition reward",
        idempotency_key=idempotency_key,
        operation_id=reward.id,
        job_id=reward.completed_job_id,
    )
    await db.execute(
        update(User)
        .where(User.id == recipient.id)
        .values(credits=User.credits + reward.credits)
        .execution_options(synchronize_session=False)
    )
    await append_server_event(
        db,
        event_name="credit_balance_changed",
        user=recipient,
        properties={"reason": reason, "delta": reward.credits},
        idempotency_key=idempotency_key,
        occurred_at=occurred_at,
    )
    return reward.credits


async def _insert_social_reward_once(db: AsyncSession, reward: AcquisitionReward) -> bool:
    values = {
        "id": reward.id,
        "user_id": reward.user_id,
        "reward_type": reward.reward_type,
        "credits": reward.credits,
        "marketing_offer_id": reward.marketing_offer_id,
        "source_user_id": reward.source_user_id,
        "completed_job_id": reward.completed_job_id,
        "occurred_at": reward.occurred_at,
    }
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        statement = postgresql_insert(AcquisitionReward).values(**values)
    elif dialect == "sqlite":
        statement = sqlite_insert(AcquisitionReward).values(**values)
    else:  # pragma: no cover - supported deployments/tests are PostgreSQL/SQLite
        raise RuntimeError(f"Unsupported acquisition reward database dialect: {dialect}")
    statement = statement.on_conflict_do_nothing(
        index_elements=[AcquisitionReward.user_id, AcquisitionReward.reward_type]
    ).returning(AcquisitionReward.id)
    return (await db.execute(statement)).scalar_one_or_none() is not None


async def claim_campaign_reward(db: AsyncSession, user: User, occurred_at: datetime) -> int:
    """Claim an active registration offer once under the recipient row lock."""
    recipient = await _lock_reward_recipient(db, user.id)
    if recipient is None or not recipient.email_verified or recipient.acquisition_offer_id is None:
        return 0
    if await _already_has_acquisition_reward(db, recipient.id):
        return 0

    offer = await db.scalar(
        select(MarketingOffer).where(
            MarketingOffer.id == recipient.acquisition_offer_id,
            MarketingOffer.code == CAMPAIGN_OFFER_CODE,
            MarketingOffer.bonus_credits == CAMPAIGN_REWARD_CREDITS,
            MarketingOffer.is_active.is_(True),
            or_(MarketingOffer.expires_at.is_(None), MarketingOffer.expires_at > occurred_at),
        )
    )
    if offer is None:
        return 0

    reward = AcquisitionReward(
        user_id=recipient.id,
        reward_type=CAMPAIGN_REWARD_TYPE,
        credits=CAMPAIGN_REWARD_CREDITS,
        marketing_offer_id=offer.id,
        occurred_at=occurred_at,
    )
    return await _credit_reward(
        db,
        recipient=recipient,
        reward=reward,
        reason=CAMPAIGN_REWARD_TYPE,
        origin="campaign_signup_reward",
        occurred_at=occurred_at,
    )


async def claim_referral_activation_reward(
    db: AsyncSession,
    referred_user: User,
    completed_job: Job,
    occurred_at: datetime,
) -> int:
    """Reward the referrer once when a verified referral finishes generation one."""
    if (
        referred_user.referred_by is None
        or not referred_user.email_verified
        or completed_job.user_id != referred_user.id
        or completed_job.completed_at is None
        or completed_job.video_url is None
    ):
        return 0

    ordinal_count = int(
        await db.scalar(
            select(func.count(Job.id)).where(
                Job.user_id == referred_user.id,
                Job.created_at <= completed_job.created_at,
            )
        )
        or 0
    )
    if ordinal_count != 1:
        return 0

    recipient = await _lock_reward_recipient(db, referred_user.referred_by)
    if recipient is None or await _already_has_acquisition_reward(db, recipient.id):
        return 0

    reward = AcquisitionReward(
        user_id=recipient.id,
        reward_type=REFERRAL_REWARD_TYPE,
        credits=REFERRAL_ACTIVATION_CREDITS,
        source_user_id=referred_user.id,
        completed_job_id=completed_job.id,
        occurred_at=occurred_at,
    )
    return await _credit_reward(
        db,
        recipient=recipient,
        reward=reward,
        reason=REFERRAL_REWARD_TYPE,
        origin="referral_activation_reward",
        occurred_at=occurred_at,
    )


async def claim_social_share_reward(
    db: AsyncSession,
    owner: User,
    completed_job: Job,
    occurred_at: datetime,
) -> int:
    """Reward an owner once after the first qualified visit to any public share."""
    if (
        completed_job.user_id != owner.id
        or completed_job.status not in {"editable", "completed"}
        or completed_job.completed_at is None
        or completed_job.video_url is None
    ):
        return 0

    recipient = await _lock_reward_recipient(db, owner.id)
    if recipient is None:
        return 0
    reward = AcquisitionReward(
        id=uuid.uuid4(),
        user_id=recipient.id,
        reward_type=SOCIAL_SHARE_REWARD_TYPE,
        credits=SOCIAL_SHARE_REWARD_CREDITS,
        completed_job_id=completed_job.id,
        occurred_at=occurred_at,
    )
    if not await _insert_social_reward_once(db, reward):
        return 0
    return await _apply_reward_credit(
        db,
        recipient=recipient,
        reward=reward,
        reason=SOCIAL_SHARE_REWARD_TYPE,
        origin="social_share_reward",
        occurred_at=occurred_at,
    )
