from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.schemas import (
    SERVER_EVENT_PROPERTY_MODELS,
    AnalyticsBatch,
    ClientEvent,
    LandingViewedEvent,
    ServerEventName,
)
from app.config import settings
from app.db.models import AnalyticsEvent, User


class AnalyticsEventConflict(Exception):
    """The same public event ID was reused for a different canonical payload."""


_SERVER_EVENT_PAGES: dict[str, str] = {
    "user_registered": "auth_register",
    "email_verified": "auth_register",
    "generation_requested": "dashboard",
    "generation_completed": "dashboard",
    "generation_failed": "dashboard",
    "video_exported": "editor",
    "checkout_started": "credits",
    "payment_completed": "credits",
    "credit_balance_changed": "dashboard",
    "second_generation_requested": "dashboard",
    "share_page_published": "dashboard",
    "share_page_visited": "viewer",
    "social_share_rewarded": "viewer",
}
_SOCIAL_SERVER_EVENTS = {"share_page_published", "share_page_visited", "social_share_rewarded"}
_CAMPAIGN_TOKEN = re.compile(r"^[a-z0-9._-]{1,100}$")
_SERVER_EVENT_NAMESPACE = uuid.UUID("e02a5d1f-3ba0-4dca-8fa2-91cc0d8bd7b6")
logger = logging.getLogger(__name__)


def canonical_payload_hash(event: ClientEvent) -> str:
    payload = json.dumps(
        event.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def derive_acquisition_source(event: ClientEvent) -> str:
    medium = event.utm_medium
    if medium in {"cpc", "ppc", "paid", "paid_social", "display"}:
        return "paid"
    if medium in {"email", "newsletter"}:
        return "email"
    if medium in {"social", "organic_social"}:
        return "social"
    if medium in {"referral", "affiliate"}:
        return "referral"
    if medium in {"organic", "seo"}:
        return "organic"
    if any((event.utm_source, event.utm_medium, event.utm_campaign, event.utm_content, event.utm_term)):
        return "campaign"
    if isinstance(event, LandingViewedEvent) and event.properties.referrer_domain:
        return "referral"
    return "direct"


def _event_values(event: ClientEvent, user: User | None) -> dict:
    return {
        "event_id": event.event_id,
        "event_name": event.event_name,
        "schema_version": event.schema_version,
        "authority": "client",
        "occurred_at": event.occurred_at,
        "received_at": datetime.now(timezone.utc),
        "anonymous_session_id": event.anonymous_session_id,
        "user_id": user.id if user else None,
        "page": event.page,
        "acquisition_source": derive_acquisition_source(event),
        "utm_source": event.utm_source,
        "utm_medium": event.utm_medium,
        "utm_campaign": event.utm_campaign,
        "utm_content": event.utm_content,
        "utm_term": event.utm_term,
        "device_class": event.device_class,
        "properties": event.properties.model_dump(mode="json"),
        "payload_hash": canonical_payload_hash(event),
    }


async def _insert_event(db: AsyncSession, values: dict) -> bool:
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        statement = postgresql_insert(AnalyticsEvent).values(**values)
    elif dialect == "sqlite":
        statement = sqlite_insert(AnalyticsEvent).values(**values)
    else:  # pragma: no cover - supported deployments/tests are PostgreSQL/SQLite
        raise RuntimeError(f"Unsupported analytics database dialect: {dialect}")

    statement = statement.on_conflict_do_nothing(index_elements=[AnalyticsEvent.event_id]).returning(
        AnalyticsEvent.event_id
    )
    inserted_id = (await db.execute(statement)).scalar_one_or_none()
    if inserted_id is not None:
        return True

    existing_hash = await db.scalar(
        select(AnalyticsEvent.payload_hash).where(AnalyticsEvent.event_id == values["event_id"])
    )
    if existing_hash != values["payload_hash"]:
        raise AnalyticsEventConflict(str(values["event_id"]))
    return False


async def ingest_client_events(
    db: AsyncSession,
    batch: AnalyticsBatch,
    user: User | None,
) -> tuple[int, int]:
    accepted = 0
    duplicates = 0
    try:
        for event in batch.events:
            if await _insert_event(db, _event_values(event, user)):
                accepted += 1
            else:
                duplicates += 1
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return accepted, duplicates


def _safe_campaign_token(value: str | None) -> str | None:
    normalized = value.strip().lower() if value else None
    return normalized if normalized and _CAMPAIGN_TOKEN.fullmatch(normalized) else None


def _server_acquisition_source(utm_source: str | None, utm_medium: str | None, utm_campaign: str | None) -> str:
    if utm_medium in {"cpc", "ppc", "paid", "paid_social", "display"}:
        return "paid"
    if utm_medium in {"email", "newsletter"}:
        return "email"
    if utm_medium in {"social", "organic_social"}:
        return "social"
    if utm_medium in {"referral", "affiliate"}:
        return "referral"
    if utm_medium in {"organic", "seo"}:
        return "organic"
    return "campaign" if any((utm_source, utm_medium, utm_campaign)) else "direct"


async def append_server_event(
    db: AsyncSession,
    *,
    event_name: ServerEventName,
    user: User | None,
    properties: dict,
    idempotency_key: str,
    occurred_at: datetime,
    anonymous_session_id: uuid.UUID | None = None,
) -> bool:
    """Append one authoritative, transaction-participating product event.

    The caller owns the transaction. A deterministic UUID makes retries safe,
    while the canonical payload hash detects accidental idempotency-key reuse.
    """
    properties_model = SERVER_EVENT_PROPERTY_MODELS.get(event_name)
    if properties_model is None:
        raise ValueError(f"Unsupported server analytics event: {event_name}")
    typed_properties = properties_model.model_validate(properties).model_dump(mode="json")
    if not idempotency_key or len(idempotency_key) > 200:
        raise ValueError("Invalid server analytics idempotency key")
    if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
        raise ValueError("Server analytics occurred_at must include a timezone")
    if event_name == "share_page_visited" and anonymous_session_id is None:
        raise ValueError("share_page_visited requires an anonymous session")
    occurred_at = occurred_at.astimezone(timezone.utc)
    if not settings.ANALYTICS_ENABLED:
        return False

    utm_source = _safe_campaign_token(user.utm_source) if user else None
    utm_medium = _safe_campaign_token(user.utm_medium) if user else None
    utm_campaign = _safe_campaign_token(user.utm_campaign) if user else None
    user_id = user.id if user else None
    acquisition_source = (
        "social"
        if event_name in _SOCIAL_SERVER_EVENTS
        else _server_acquisition_source(utm_source, utm_medium, utm_campaign)
    )
    event_id = uuid.uuid5(_SERVER_EVENT_NAMESPACE, f"v1:{event_name}:{idempotency_key}")
    canonical = {
        "event_id": str(event_id),
        "event_name": event_name,
        "schema_version": 1,
        "authority": "server",
        "occurred_at": occurred_at.isoformat(),
        "anonymous_session_id": str(anonymous_session_id) if anonymous_session_id else None,
        "user_id": str(user_id) if user_id else None,
        "page": _SERVER_EVENT_PAGES[event_name],
        "acquisition_source": acquisition_source,
        "utm_source": utm_source,
        "utm_medium": utm_medium,
        "utm_campaign": utm_campaign,
        "device_class": "unknown",
        "properties": typed_properties,
    }
    payload_hash = hashlib.sha256(
        json.dumps(canonical, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).hexdigest()
    return await _insert_event(
        db,
        {
            **canonical,
            "event_id": event_id,
            "occurred_at": occurred_at,
            "received_at": datetime.now(timezone.utc),
            "anonymous_session_id": anonymous_session_id,
            "user_id": user_id,
            "utm_content": None,
            "utm_term": None,
            "payload_hash": payload_hash,
        },
    )


async def append_server_event_safely(
    db: AsyncSession,
    *,
    event_name: ServerEventName,
    user: User,
    properties: dict,
    idempotency_key: str,
    occurred_at: datetime,
) -> bool:
    """Append inside a savepoint so analytics can never block core state."""
    try:
        async with db.begin_nested():
            return await append_server_event(
                db,
                event_name=event_name,
                user=user,
                properties=properties,
                idempotency_key=idempotency_key,
                occurred_at=occurred_at,
            )
    except Exception:  # noqa: BLE001 - non-critical telemetry must not poison the caller transaction
        logger.exception("Failed to append authoritative analytics event %s", event_name)
        return False
