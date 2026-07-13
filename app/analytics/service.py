from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.schemas import AnalyticsBatch, ClientEvent, LandingViewedEvent
from app.db.models import AnalyticsEvent, User


class AnalyticsEventConflict(Exception):
    """The same public event ID was reused for a different canonical payload."""


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
