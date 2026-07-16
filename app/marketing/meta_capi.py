"""Consent-gated Meta Conversions API outbox."""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import AsyncIterator

import httpx
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import MetaConversionOutbox, User
from app.marketing.export import pseudonymous_customer_ref

_SUPPORTED_EVENTS = {"CompleteRegistration", "Purchase"}
_API_VERSION = re.compile(r"^v\d+\.\d+$")
_DISPATCH_TIMEOUT_SECONDS = 5.0
_DISPATCH_LEASE_SECONDS = 30
_MAX_ATTEMPTS = 5
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _ClaimedConversion:
    id: uuid.UUID
    user_id: uuid.UUID
    payload: dict
    attempts: int
    lease_token: str


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
            MetaConversionOutbox.status.in_(("pending", "retry", "dispatching")),
        )
        .values(
            status="cancelled",
            last_error=reason[:255],
            lease_token=None,
            lease_until=None,
        )
    )
    return int(result.rowcount or 0)


@asynccontextmanager
async def _dispatch_client(client: httpx.AsyncClient | None) -> AsyncIterator[httpx.AsyncClient]:
    if client is not None:
        yield client
        return
    async with httpx.AsyncClient() as created:
        yield created


def _due_predicate(attempted_at: datetime):
    return or_(
        and_(
            MetaConversionOutbox.status.in_(("pending", "retry")),
            MetaConversionOutbox.next_attempt_at <= attempted_at,
        ),
        and_(
            MetaConversionOutbox.status == "dispatching",
            MetaConversionOutbox.lease_until.is_not(None),
            MetaConversionOutbox.lease_until <= attempted_at,
        ),
    )


def _user_allows_delivery(user: User | None) -> bool:
    return bool(user is not None and user.marketing_measurement_consented_at is not None and user.plan != "deleted")


async def _unsupported_dispatch(
    db: AsyncSession,
    *,
    attempted_at: datetime,
    limit: int,
) -> int:
    """SQLite can cancel ineligible rows but never claims or delivers them."""
    rows = list(
        await db.scalars(
            select(MetaConversionOutbox)
            .where(_due_predicate(attempted_at))
            .order_by(MetaConversionOutbox.next_attempt_at, MetaConversionOutbox.created_at)
            .limit(limit)
        )
    )
    cancelled = 0
    for row in rows:
        if _user_allows_delivery(await db.get(User, row.user_id)):
            continue
        row.status = "cancelled"
        row.last_error = "consent_revoked"
        row.lease_token = None
        row.lease_until = None
        cancelled += 1
    if cancelled:
        await db.commit()
    else:
        await db.rollback()
    return cancelled


async def _claim_due_conversions(
    db: AsyncSession,
    *,
    attempted_at: datetime,
    limit: int,
) -> tuple[list[_ClaimedConversion], int]:
    """Claim under SKIP LOCKED and release every DB lock before HTTP."""
    rows = list(
        await db.scalars(
            select(MetaConversionOutbox)
            .where(_due_predicate(attempted_at))
            .order_by(MetaConversionOutbox.next_attempt_at, MetaConversionOutbox.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    claimed: list[_ClaimedConversion] = []
    cancelled = 0
    for row in rows:
        if not _user_allows_delivery(await db.get(User, row.user_id)):
            row.status = "cancelled"
            row.last_error = "consent_revoked"
            row.lease_token = None
            row.lease_until = None
            cancelled += 1
            continue
        lease_token = str(uuid.uuid4())
        row.status = "dispatching"
        row.lease_token = lease_token
        row.lease_until = attempted_at + timedelta(seconds=_DISPATCH_LEASE_SECONDS)
        claimed.append(
            _ClaimedConversion(
                id=row.id,
                user_id=row.user_id,
                payload=row.payload,
                attempts=row.attempts,
                lease_token=lease_token,
            )
        )
    await db.commit()
    return claimed, cancelled


async def _recheck_claim(db: AsyncSession, claim: _ClaimedConversion) -> str:
    """Recheck account and cancellation state, then end the read transaction."""
    row = (
        await db.execute(
            select(
                MetaConversionOutbox.status,
                MetaConversionOutbox.lease_token,
                User.marketing_measurement_consented_at,
                User.plan,
            )
            .join(User, User.id == MetaConversionOutbox.user_id, isouter=True)
            .where(MetaConversionOutbox.id == claim.id)
        )
    ).one_or_none()
    await db.rollback()
    if row is None:
        return "lost"
    if row.status != "dispatching" or row.lease_token != claim.lease_token:
        return "cancelled" if row.status == "cancelled" else "lost"
    if row.marketing_measurement_consented_at is not None and row.plan != "deleted":
        return "deliver"
    cancelled = await db.execute(
        update(MetaConversionOutbox)
        .where(
            MetaConversionOutbox.id == claim.id,
            MetaConversionOutbox.status == "dispatching",
            MetaConversionOutbox.lease_token == claim.lease_token,
        )
        .values(
            status="cancelled",
            last_error="consent_revoked",
            lease_token=None,
            lease_until=None,
        )
    )
    await db.commit()
    return "cancelled" if cancelled.rowcount else "lost"


async def _finalize_claims(
    db: AsyncSession,
    claims: list[_ClaimedConversion],
    *,
    attempted_at: datetime,
    error: str | None,
) -> dict[str, int]:
    stats = {"sent": 0, "retried": 0, "failed": 0, "cancelled": 0}
    missed: list[uuid.UUID] = []
    for claim in claims:
        attempts = claim.attempts + 1
        if error is None:
            values = {
                "status": "sent",
                "attempts": attempts,
                "last_attempt_at": attempted_at,
                "last_error": None,
                "sent_at": attempted_at,
                "lease_token": None,
                "lease_until": None,
            }
            outcome = "sent"
        elif attempts >= _MAX_ATTEMPTS:
            values = {
                "status": "failed",
                "attempts": attempts,
                "last_attempt_at": attempted_at,
                "last_error": error,
                "lease_token": None,
                "lease_until": None,
            }
            outcome = "failed"
        else:
            values = {
                "status": "retry",
                "attempts": attempts,
                "next_attempt_at": attempted_at + timedelta(seconds=60 * (2 ** (attempts - 1))),
                "last_attempt_at": attempted_at,
                "last_error": error,
                "lease_token": None,
                "lease_until": None,
            }
            outcome = "retried"
        updated = await db.execute(
            update(MetaConversionOutbox)
            .where(
                MetaConversionOutbox.id == claim.id,
                MetaConversionOutbox.status == "dispatching",
                MetaConversionOutbox.lease_token == claim.lease_token,
            )
            .values(**values)
        )
        if updated.rowcount:
            stats[outcome] += 1
        else:
            missed.append(claim.id)
    await db.commit()
    if missed:
        cancelled = int(
            await db.scalar(
                select(func.count())
                .select_from(MetaConversionOutbox)
                .where(
                    MetaConversionOutbox.id.in_(missed),
                    MetaConversionOutbox.status == "cancelled",
                )
            )
            or 0
        )
        stats["cancelled"] += cancelled
        await db.rollback()
    return stats


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
    dialect = db.get_bind().dialect.name
    if dialect != "postgresql":
        stats["unsupported"] = 1
        stats["cancelled"] = await _unsupported_dispatch(db, attempted_at=attempted_at, limit=limit)
        return stats
    claimed, cancelled = await _claim_due_conversions(db, attempted_at=attempted_at, limit=limit)
    stats["cancelled"] += cancelled
    if not claimed:
        return stats

    deliverable: list[_ClaimedConversion] = []
    for claim in claimed:
        state = await _recheck_claim(db, claim)
        if state == "deliver":
            deliverable.append(claim)
        elif state == "cancelled":
            stats["cancelled"] += 1
    if not deliverable:
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
        finalized = await _finalize_claims(db, deliverable, attempted_at=attempted_at, error=error)
        for key, value in finalized.items():
            stats[key] += value
        return stats
    finalized = await _finalize_claims(db, deliverable, attempted_at=attempted_at, error=None)
    for key, value in finalized.items():
        stats[key] += value
    return stats
