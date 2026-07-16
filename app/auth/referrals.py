from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


async def award_verified_referral(db: AsyncSession, referred_user: User) -> int:
    """Retired compatibility hook; verification no longer creates referral awards."""
    del db, referred_user
    return 0
