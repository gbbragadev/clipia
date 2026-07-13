from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PasswordResetToken


async def consume_password_reset_token(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    jti: uuid.UUID,
    used_at: datetime,
) -> bool:
    consumed = await db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.jti == jti,
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > used_at,
        )
        .values(used_at=used_at)
        .returning(PasswordResetToken.jti)
    )
    return consumed.scalar_one_or_none() is not None


async def invalidate_password_reset_tokens(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    used_at: datetime,
) -> None:
    await db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=used_at)
    )
