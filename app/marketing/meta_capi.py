"""Consent-gated Meta Conversions API outbox."""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import AsyncIterator

import httpx
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import MetaConversionOutbox, User
from app.marketing.export import pseudonymous_customer_ref

_SUPPORTED_EVENTS = {"CompleteRegistration", "Purchase"}
_API_VERSION = re.compile(r"^v\d+\.\d+$")
_DISPATCH_TIMEOUT_SECONDS = 5.0
_MAX_ATTEMPTS = 5
logger = logging.getLogger(__name__)


def _meta_configured() -> bool:
    return bool(
        settings.META_CAPI_ENABLED
        and settings.META_CAPI_PIXEL_ID.strip()
        and settings.META_CAPI_ACCESS_TOKEN.get_secret_value().strip()
        and settings.MARKETING_PSEUDONYM_SECRET.get_secret_value().strip()
        and _API_VERSION.fullmatch(settings.META_CAPI_API_VERSION.strip())
    )


def _hashed_email(email: str) -> str:
    normalized = email.strip().lower().encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


async def enqueue_meta_conversion(
    db: AsyncSession,
    *,
    user: User,
    event_name: str,
    event_id: str,
    value_brl: Decimal | float | int | None = None,
) -> bool:
    """Append one already-hashed Meta event without committing the caller transaction."""
    if not _meta_configured() or user.marketing_measurement_consented_at is None:
        return False
    if event_name not in _SUPPORTED_EVENTS:
        raise ValueError(f"Unsupported Meta conversion event: {event_name}")
    event_id = event_id.strip()
    if not event_id or len(event_id) > 100:
        raise ValueError("Invalid Meta conversion event ID")

    payload: dict = {
        "event_name": event_name,
        "event_time": int(datetime.now(timezone.utc).timestamp()),
        "event_id": event_id,
        "action_source": "website",
        "user_data": {
            "em": [_hashed_email(user.email)],
            "external_id": [pseudonymous_customer_ref(f"meta:{user.id}")],
        },
    }
    if event_name == "Purchase":
        if value_brl is None or Decimal(str(value_brl)) <= 0:
            raise ValueError("Purchase requires a positive BRL value")
        payload["custom_data"] = {
            "currency": "BRL",
            "value": round(float(Decimal(str(value_brl))), 2),
        }

    values = {
        "user_id": user.id,
        "event_id": event_id,
        "event_name": event_name,
        "payload": payload,
        "status": "pending",
        "attempts": 0,
        "next_attempt_at": datetime.now(timezone.utc),
    }
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        statement = postgresql_insert(MetaConversionOutbox).values(**values)
    elif dialect == "sqlite":
        statement = sqlite_insert(MetaConversionOutbox).values(**values)
    else:  # pragma: no cover - supported deployments/tests are PostgreSQL/SQLite
        raise RuntimeError(f"Unsupported Meta outbox database dialect: {dialect}")
    inserted = (
        await db.execute(
            statement.on_conflict_do_nothing(index_elements=[MetaConversionOutbox.event_id]).returning(
                MetaConversionOutbox.id
            )
        )
    ).scalar_one_or_none()
    return inserted is not None


async def enqueue_meta_conversion_safely(
    db: AsyncSession,
    *,
    user: User,
    event_name: str,
    event_id: str,
    value_brl: Decimal | float | int | None = None,
) -> bool:
    """Keep measurement failures inside a savepoint owned by the core transaction."""
    try:
        async with db.begin_nested():
            return await enqueue_meta_conversion(
                db,
                user=user,
                event_name=event_name,
                event_id=event_id,
                value_brl=value_brl,
            )
    except Exception as exc:  # noqa: BLE001 - optional marketing must not poison signup/payment
        logger.error(
            "Failed to enqueue Meta conversion %s (error_type=%s)",
            event_name,
            exc.__class__.__name__,
        )
        return False


async def cancel_pending_meta_conversions(db: AsyncSession, *, user_id: uuid.UUID, reason: str) -> int:
    """Cancel unsent events when measurement consent or the account is withdrawn."""
    result = await db.execute(
        update(MetaConversionOutbox)
        .where(
            MetaConversionOutbox.user_id == user_id,
            MetaConversionOutbox.status.in_(("pending", "retry")),
        )
        .values(status="cancelled", last_error=reason[:255])
    )
    return int(result.rowcount or 0)


@asynccontextmanager
async def _dispatch_client(client: httpx.AsyncClient | None) -> AsyncIterator[httpx.AsyncClient]:
    if client is not None:
        yield client
        return
    async with httpx.AsyncClient() as created:
        yield created


async def dispatch_pending_meta_conversions(
    db: AsyncSession,
    *,
    client: httpx.AsyncClient | None = None,
    limit: int = 100,
) -> dict[str, int]:
    """Deliver one due batch; Postgres workers skip rows locked by another dispatcher."""
    stats = {"sent": 0, "retried": 0, "failed": 0, "cancelled": 0, "unsupported": 0}
    if not _meta_configured():
        return stats
    if limit < 1 or limit > 100:
        raise ValueError("Meta dispatch limit must be between 1 and 100")

    attempted_at = datetime.now(timezone.utc)
    statement = (
        select(MetaConversionOutbox)
        .where(
            MetaConversionOutbox.status.in_(("pending", "retry")),
            MetaConversionOutbox.next_attempt_at <= attempted_at,
        )
        .order_by(MetaConversionOutbox.next_attempt_at, MetaConversionOutbox.created_at)
        .limit(limit)
    )
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        statement = statement.with_for_update(skip_locked=True)
    rows = list(await db.scalars(statement))
    if not rows:
        return stats

    deliverable = []
    for row in rows:
        user_statement = select(User).where(User.id == row.user_id)
        if dialect == "postgresql":
            user_statement = user_statement.with_for_update()
        user = await db.scalar(user_statement)
        if user is None or user.marketing_measurement_consented_at is None or user.plan == "deleted":
            row.status = "cancelled"
            row.last_error = "consent_revoked"
            stats["cancelled"] += 1
        else:
            deliverable.append(row)

    if dialect != "postgresql":
        stats["unsupported"] = 1
        if stats["cancelled"]:
            await db.commit()
        else:
            await db.rollback()
        return stats
    if not deliverable:
        await db.commit()
        return stats

    url = (
        f"https://graph.facebook.com/{settings.META_CAPI_API_VERSION.strip()}/"
        f"{settings.META_CAPI_PIXEL_ID.strip()}/events"
    )
    try:
        async with _dispatch_client(client) as http_client:
            response = await http_client.post(
                url,
                json={"data": [row.payload for row in deliverable]},
                headers={"Authorization": f"Bearer {settings.META_CAPI_ACCESS_TOKEN.get_secret_value().strip()}"},
                timeout=_DISPATCH_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
    except Exception as exc:  # noqa: BLE001 - delivery state must remain durable for any client failure
        # Exception messages may echo request data or credentials. Persist only
        # a bounded diagnostic code; detailed context stays in protected logs.
        error = exc.__class__.__name__[:255]
        for row in deliverable:
            row.attempts += 1
            row.last_attempt_at = attempted_at
            row.last_error = error
            if row.attempts >= _MAX_ATTEMPTS:
                row.status = "failed"
                stats["failed"] += 1
            else:
                row.status = "retry"
                row.next_attempt_at = attempted_at + timedelta(seconds=60 * (2 ** (row.attempts - 1)))
                stats["retried"] += 1
        await db.commit()
        return stats

    for row in deliverable:
        row.attempts += 1
        row.status = "sent"
        row.last_attempt_at = attempted_at
        row.last_error = None
        row.sent_at = attempted_at
        stats["sent"] += 1
    await db.commit()
    return stats
