from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.service import append_server_event_safely
from app.db.models import ReferralCreditAward, User
from app.services.credit_ledger import set_credit_ledger_context

MAX_REFERRAL_BONUS_COUNT = 10
REFERRAL_BONUS_CREDITS = 2


async def award_verified_referral(db: AsyncSession, referred_user: User) -> int:
    """Claim and credit one referral award under the referrer's row lock."""
    if referred_user.referred_by is None:
        return 0

    referrer = await db.scalar(select(User).where(User.id == referred_user.referred_by).with_for_update())
    if referrer is None:
        return 0

    existing = await db.scalar(
        select(ReferralCreditAward.id).where(ReferralCreditAward.referred_user_id == referred_user.id)
    )
    if existing is not None:
        return 0

    awarded_count = int(
        await db.scalar(
            select(func.count(ReferralCreditAward.id)).where(ReferralCreditAward.referrer_user_id == referrer.id)
        )
        or 0
    )
    if awarded_count >= MAX_REFERRAL_BONUS_COUNT:
        return 0

    award = ReferralCreditAward(
        referred_user_id=referred_user.id,
        referrer_user_id=referrer.id,
        credits=REFERRAL_BONUS_CREDITS,
    )
    db.add(award)
    await db.flush()
    await set_credit_ledger_context(
        db,
        origin="referral_bonus",
        reason="verified referral bonus",
        idempotency_key=f"referral:{referred_user.id}",
        operation_id=award.id,
    )
    await db.execute(update(User).where(User.id == referrer.id).values(credits=User.credits + REFERRAL_BONUS_CREDITS))
    await append_server_event_safely(
        db,
        event_name="credit_balance_changed",
        user=referrer,
        properties={"reason": "referral", "delta": REFERRAL_BONUS_CREDITS},
        idempotency_key=f"referral:{referred_user.id}:credit",
        occurred_at=datetime.now(timezone.utc),
    )
    return REFERRAL_BONUS_CREDITS
