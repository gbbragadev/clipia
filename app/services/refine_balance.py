from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RefineBalanceOutbox, User

_PROJECT_REFINEMENT_LUA = """
local current = tonumber(redis.call('GET', KEYS[2]) or '-1')
local incoming = tonumber(ARGV[1])
if current > incoming then
  return -1
end
local current_balance = tonumber(redis.call('GET', KEYS[1]) or '')
local incoming_balance = tonumber(ARGV[2])
if current == incoming and current_balance and math.abs(current_balance - incoming_balance) < 0.000001 then
  return 0
end
redis.call('SET', KEYS[1], ARGV[2])
redis.call('SET', KEYS[2], ARGV[1])
return 1
"""


async def adjust_refine_balance(
    session: AsyncSession,
    user_id: uuid.UUID,
    delta: float,
) -> RefineBalanceOutbox:
    """Adjust the SQL source of truth and append its rollback-compatible projection."""
    result = await session.execute(
        update(User)
        .where(User.id == user_id, User.script_refine_pending + delta >= 0)
        .values(
            script_refine_pending=User.script_refine_pending + delta,
            script_refine_version=User.script_refine_version + 1,
        )
        .returning(User.script_refine_pending, User.script_refine_version)
    )
    row = result.one_or_none()
    if row is None:
        raise ValueError("refine balance adjustment would be negative or user is missing")
    balance_after, version = row
    return await queue_refine_balance_projection(
        session,
        user_id=user_id,
        version=int(version),
        balance_after=float(balance_after),
    )


async def queue_refine_balance_projection(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    version: int,
    balance_after: float,
) -> RefineBalanceOutbox:
    projection = RefineBalanceOutbox(
        id=uuid.uuid4(),
        user_id=user_id,
        version=version,
        balance_after=round(float(balance_after), 2),
    )
    session.add(projection)
    await session.flush()
    return projection


def _apply_projection_values(redis, user_id: uuid.UUID, version: int, balance_after: float) -> int:
    balance_key = f"script_refine_pending:{user_id}"
    version_key = f"script_refine_pending_version:{user_id}"
    balance = format(float(balance_after), ".2f")
    if hasattr(redis, "eval"):
        return int(redis.eval(_PROJECT_REFINEMENT_LUA, 2, balance_key, version_key, version, balance))

    # Minimal compatibility for the in-memory test adapter. Production redis-py
    # always uses the atomic Lua branch above.
    current = int(redis.get(version_key) or -1)
    if current > version:
        return -1
    current_balance = redis.get(balance_key)
    if current == version and current_balance is not None and abs(float(current_balance) - float(balance)) < 0.000001:
        return 0
    redis.set(balance_key, balance)
    redis.set(version_key, str(version))
    return 1


def _apply_projection(redis, projection: RefineBalanceOutbox) -> bool:
    return (
        _apply_projection_values(
            redis,
            projection.user_id,
            int(projection.version),
            float(projection.balance_after),
        )
        == 1
    )


def ensure_refine_balance_projection(
    redis,
    *,
    user_id: uuid.UUID,
    version: int,
    balance_after: float,
) -> bool:
    """Repair and then verify the exact legacy key used by pre-SQL binaries."""
    outcome = _apply_projection_values(redis, user_id, version, balance_after)
    balance_key = f"script_refine_pending:{user_id}"
    version_key = f"script_refine_pending_version:{user_id}"
    actual_balance = redis.get(balance_key)
    actual_version = redis.get(version_key)
    if (
        outcome < 0
        or actual_balance is None
        or actual_version is None
        or int(actual_version) != version
        or abs(float(actual_balance) - float(balance_after)) >= 0.000001
    ):
        raise RuntimeError(f"legacy refine projection mismatch for user {user_id}")
    return outcome == 1


async def sync_refine_balance_projection(
    session: AsyncSession,
    projection_id: uuid.UUID,
    redis,
) -> bool:
    result = await session.execute(
        select(RefineBalanceOutbox)
        .where(RefineBalanceOutbox.id == projection_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    projection = result.scalar_one_or_none()
    if projection is None or projection.applied_at is not None:
        return False
    try:
        changed = _apply_projection(redis, projection)
    except Exception as exc:  # noqa: BLE001 - the durable row is the retry contract
        projection.last_error = repr(exc)
        await session.commit()
        return False
    projection.applied_at = datetime.now(timezone.utc)
    projection.last_error = None
    await session.commit()
    return changed
