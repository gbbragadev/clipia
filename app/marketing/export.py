from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import json
import re
import uuid
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import AnalyticsEvent, CreditPurchase, User
from app.marketing.schemas import (
    Attribution,
    FunnelCount,
    MarketingConversion,
    MarketingConversionPage,
    MarketingSummary,
    RevenueSummary,
    SourceCount,
)
from app.payments.states import canonical_payment_state_expression

_CONVERSION_EVENT_NAMES = (
    "user_registered",
    "email_verified",
    "generation_completed",
    "video_exported",
    "checkout_started",
)
_ATTRIBUTION_TOKEN = re.compile(r"^[a-z0-9._-]{1,100}$")


def pseudonymous_customer_ref(identifier: uuid.UUID | str, secret: str | None = None) -> str:
    key = (secret if secret is not None else settings.MARKETING_PSEUDONYM_SECRET).encode("utf-8")
    if not key:
        raise ValueError("MARKETING_PSEUDONYM_SECRET is not configured")
    normalized = str(identifier).strip().lower().encode("utf-8")
    return hmac.new(key, normalized, hashlib.sha256).hexdigest()


def _bounds(from_date: date, to_date: date) -> tuple[datetime, datetime]:
    return (
        datetime.combine(from_date, time.min, tzinfo=timezone.utc),
        datetime.combine(to_date + timedelta(days=1), time.min, tzinfo=timezone.utc),
    )


async def build_marketing_summary(db: AsyncSession, *, from_date: date, to_date: date) -> MarketingSummary:
    start, end = _bounds(from_date, to_date)
    funnel_rows = (
        await db.execute(
            select(AnalyticsEvent.event_name, func.count())
            .where(AnalyticsEvent.occurred_at >= start, AnalyticsEvent.occurred_at < end)
            .group_by(AnalyticsEvent.event_name)
            .order_by(AnalyticsEvent.event_name)
        )
    ).all()
    source_rows = (
        await db.execute(
            select(AnalyticsEvent.acquisition_source, func.count())
            .where(AnalyticsEvent.occurred_at >= start, AnalyticsEvent.occurred_at < end)
            .group_by(AnalyticsEvent.acquisition_source)
            .order_by(AnalyticsEvent.acquisition_source)
        )
    ).all()
    paid_state = canonical_payment_state_expression(CreditPurchase.status, CreditPurchase.payment_state)
    paid_count, gross_cents = (
        await db.execute(
            select(func.count(CreditPurchase.id), func.coalesce(func.sum(CreditPurchase.price_brl), 0)).where(
                paid_state == "paid",
                CreditPurchase.paid_at.is_not(None),
                CreditPurchase.paid_at >= start,
                CreditPurchase.paid_at < end,
            )
        )
    ).one()
    return MarketingSummary(
        from_date=from_date,
        to_date=to_date,
        funnel=[FunnelCount(event_type=name, count=count) for name, count in funnel_rows],
        sources=[SourceCount(acquisition_source=source, count=count) for source, count in source_rows],
        revenue=RevenueSummary(
            approved_purchases=int(paid_count),
            gross_amount=round(int(gross_cents) / 100, 2),
        ),
    )


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _encode_cursor(item: MarketingConversion) -> str:
    raw = json.dumps(
        {"occurred_at": item.occurred_at.isoformat(), "event_id": item.event_id},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str | None) -> tuple[datetime, str] | None:
    if not cursor:
        return None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.b64decode(padded, altchars=b"-_", validate=True))
        occurred_at = _as_utc(datetime.fromisoformat(payload["occurred_at"]))
        event_id = str(payload["event_id"])
        if not event_id or len(event_id) > 100:
            raise ValueError
        return occurred_at, event_id
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid marketing cursor") from exc


def _safe_attribution_token(value: str | None) -> str | None:
    normalized = value.strip().lower() if value else None
    if not normalized or not _ATTRIBUTION_TOKEN.fullmatch(normalized):
        return None
    if "token" in normalized or "secret" in normalized:
        return None
    try:
        ipaddress.ip_address(normalized)
    except ValueError:
        return normalized
    return None


def _attribution(row: AnalyticsEvent | User) -> Attribution:
    utm_source = _safe_attribution_token(row.utm_source)
    utm_medium = _safe_attribution_token(row.utm_medium)
    utm_campaign = _safe_attribution_token(row.utm_campaign)
    source = getattr(row, "acquisition_source", None)
    if source is None:
        if utm_medium in {"cpc", "ppc", "paid", "paid_social", "display"}:
            source = "paid"
        elif utm_medium in {"email", "newsletter"}:
            source = "email"
        elif utm_medium in {"social", "organic_social"}:
            source = "social"
        elif utm_medium in {"referral", "affiliate"}:
            source = "referral"
        elif utm_medium in {"organic", "seo"}:
            source = "organic"
        else:
            source = "campaign" if any((utm_source, utm_medium, utm_campaign)) else "direct"
    return Attribution(
        acquisition_source=source,
        utm_source=utm_source,
        utm_medium=utm_medium,
        utm_campaign=utm_campaign,
        utm_content=_safe_attribution_token(getattr(row, "utm_content", None)),
        utm_term=_safe_attribution_token(getattr(row, "utm_term", None)),
    )


async def build_marketing_conversions(
    db: AsyncSession,
    *,
    cursor: str | None,
    limit: int,
) -> MarketingConversionPage:
    boundary = _decode_cursor(cursor)
    timestamp_boundary = boundary[0] if boundary else None
    analytics_query = select(AnalyticsEvent).where(
        AnalyticsEvent.user_id.is_not(None),
        AnalyticsEvent.event_name.in_(_CONVERSION_EVENT_NAMES),
    )
    paid_state = canonical_payment_state_expression(CreditPurchase.status, CreditPurchase.payment_state)
    purchase_query = (
        select(CreditPurchase, User)
        .join(User, User.id == CreditPurchase.user_id)
        .where(paid_state == "paid", CreditPurchase.paid_at.is_not(None))
    )
    if timestamp_boundary is not None:
        analytics_query = analytics_query.where(AnalyticsEvent.occurred_at <= timestamp_boundary)
        purchase_query = purchase_query.where(CreditPurchase.paid_at <= timestamp_boundary)

    analytics_rows = list(
        await db.scalars(analytics_query.order_by(AnalyticsEvent.occurred_at.desc()).limit(limit + 1))
    )
    purchase_rows = (await db.execute(purchase_query.order_by(CreditPurchase.paid_at.desc()).limit(limit + 1))).all()

    items = [
        MarketingConversion(
            event_id=f"analytics:{row.event_id}",
            event_type=row.event_name,
            occurred_at=_as_utc(row.occurred_at),
            customer_ref=pseudonymous_customer_ref(row.user_id),
            attribution=_attribution(row),
        )
        for row in analytics_rows
    ]
    items.extend(
        MarketingConversion(
            event_id=f"purchase:{purchase.id}",
            event_type="Purchase",
            occurred_at=_as_utc(purchase.paid_at),
            customer_ref=pseudonymous_customer_ref(purchase.user_id),
            amount=round(purchase.price_brl / 100, 2),
            currency=purchase.currency,
            attribution=_attribution(user),
        )
        for purchase, user in purchase_rows
        if purchase.paid_at is not None
    )
    items.sort(key=lambda item: (item.occurred_at, item.event_id), reverse=True)
    if boundary is not None:
        boundary_time, boundary_id = boundary
        items = [item for item in items if (item.occurred_at, item.event_id) < (boundary_time, boundary_id)]
    page_items = items[:limit]
    next_cursor = _encode_cursor(page_items[-1]) if len(items) > limit and page_items else None
    return MarketingConversionPage(items=page_items, next_cursor=next_cursor)
