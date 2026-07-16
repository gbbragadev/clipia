from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
import uuid
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import Integer, String, and_, cast, func, literal, null, or_, select, union_all
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
_ATTRIBUTION_ALLOWLISTS: dict[str, frozenset[str]] = {
    "utm_source": frozenset({"meta", "instagram", "tiktok", "youtube"}),
    "utm_medium": frozenset({"paid_social", "organic_social"}),
    "utm_campaign": frozenset({"clipia_creator20_pilot", "creator20_v1"}),
    "utm_content": frozenset({"share", "v-page"}),
    "utm_term": frozenset(),
}
_CURSOR_CONTEXT = b"clipia-marketing-cursor:v1:"
_CUSTOMER_CONTEXT = b"clipia-marketing-customer:v1:"
_CURSOR_VERSION = 1
_CURSOR_EVENT_ID = re.compile(r"^(analytics|purchase):[0-9a-f]{8}-[0-9a-f-]{27}$")
_EARLIEST_CURSOR_TIME = datetime(2020, 1, 1, tzinfo=timezone.utc)


def pseudonymous_customer_ref(identifier: uuid.UUID | str, secret: str | None = None) -> str:
    secret_value = secret if secret is not None else settings.MARKETING_PSEUDONYM_SECRET.get_secret_value()
    key = secret_value.encode("utf-8")
    if not key:
        raise ValueError("MARKETING_PSEUDONYM_SECRET is not configured")
    normalized = str(identifier).strip().lower().encode("utf-8")
    return hmac.new(key, _CUSTOMER_CONTEXT + normalized, hashlib.sha256).hexdigest()


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
    payload = json.dumps(
        {"v": _CURSOR_VERSION, "t": item.occurred_at.isoformat(), "e": item.event_id},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    encoded_payload = base64.urlsafe_b64encode(payload).rstrip(b"=")
    secret = settings.MARKETING_PSEUDONYM_SECRET.get_secret_value().encode("utf-8")
    if not secret:
        raise ValueError("MARKETING_PSEUDONYM_SECRET is not configured")
    signature = hmac.new(secret, _CURSOR_CONTEXT + encoded_payload, hashlib.sha256).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=")
    return f"{encoded_payload.decode('ascii')}.{encoded_signature.decode('ascii')}"


def _decode_cursor(cursor: str | None) -> tuple[datetime, str] | None:
    if not cursor:
        return None
    try:
        if len(cursor) > 512 or cursor.count(".") != 1:
            raise ValueError
        encoded_payload, encoded_signature = cursor.split(".")
        payload_bytes = base64.b64decode(
            encoded_payload + "=" * (-len(encoded_payload) % 4), altchars=b"-_", validate=True
        )
        signature = base64.b64decode(
            encoded_signature + "=" * (-len(encoded_signature) % 4), altchars=b"-_", validate=True
        )
        secret = settings.MARKETING_PSEUDONYM_SECRET.get_secret_value().encode("utf-8")
        expected = hmac.new(secret, _CURSOR_CONTEXT + encoded_payload.encode("ascii"), hashlib.sha256).digest()
        if len(signature) != len(expected) or not hmac.compare_digest(signature, expected):
            raise ValueError
        payload = json.loads(payload_bytes)
        if not isinstance(payload, dict) or set(payload) != {"v", "t", "e"} or payload["v"] != _CURSOR_VERSION:
            raise ValueError
        occurred_at = datetime.fromisoformat(payload["t"])
        if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
            raise ValueError
        occurred_at = occurred_at.astimezone(timezone.utc)
        if not _EARLIEST_CURSOR_TIME <= occurred_at <= datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError
        event_id = str(payload["e"])
        if not _CURSOR_EVENT_ID.fullmatch(event_id):
            raise ValueError
        return occurred_at, event_id
    except (binascii.Error, KeyError, OverflowError, TypeError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid marketing cursor") from exc


def _safe_attribution_token(field: str, value: str | None) -> str | None:
    normalized = value.strip().lower() if value else None
    return normalized if normalized in _ATTRIBUTION_ALLOWLISTS[field] else None


def _attribution(
    *,
    acquisition_source: str | None,
    utm_source: str | None,
    utm_medium: str | None,
    utm_campaign: str | None,
    utm_content: str | None,
    utm_term: str | None,
) -> Attribution:
    utm_source = _safe_attribution_token("utm_source", utm_source)
    utm_medium = _safe_attribution_token("utm_medium", utm_medium)
    utm_campaign = _safe_attribution_token("utm_campaign", utm_campaign)
    utm_content = _safe_attribution_token("utm_content", utm_content)
    utm_term = _safe_attribution_token("utm_term", utm_term)
    source = acquisition_source
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
        utm_content=utm_content,
        utm_term=utm_term,
    )


async def build_marketing_conversions(
    db: AsyncSession,
    *,
    cursor: str | None,
    limit: int,
) -> MarketingConversionPage:
    boundary = _decode_cursor(cursor)
    analytics_rows = select(
        (literal("analytics:") + cast(AnalyticsEvent.event_id, String(36))).label("event_id"),
        AnalyticsEvent.event_name.label("event_type"),
        AnalyticsEvent.occurred_at.label("occurred_at"),
        AnalyticsEvent.user_id.label("customer_id"),
        cast(null(), Integer).label("amount_cents"),
        cast(null(), String(3)).label("currency"),
        AnalyticsEvent.acquisition_source.label("acquisition_source"),
        AnalyticsEvent.utm_source.label("utm_source"),
        AnalyticsEvent.utm_medium.label("utm_medium"),
        AnalyticsEvent.utm_campaign.label("utm_campaign"),
        AnalyticsEvent.utm_content.label("utm_content"),
        AnalyticsEvent.utm_term.label("utm_term"),
    ).where(AnalyticsEvent.user_id.is_not(None), AnalyticsEvent.event_name.in_(_CONVERSION_EVENT_NAMES))
    paid_state = canonical_payment_state_expression(CreditPurchase.status, CreditPurchase.payment_state)
    purchase_rows = (
        select(
            (literal("purchase:") + cast(CreditPurchase.id, String(36))).label("event_id"),
            literal("Purchase").label("event_type"),
            CreditPurchase.paid_at.label("occurred_at"),
            CreditPurchase.user_id.label("customer_id"),
            CreditPurchase.price_brl.label("amount_cents"),
            CreditPurchase.currency.label("currency"),
            cast(null(), String(20)).label("acquisition_source"),
            User.utm_source.label("utm_source"),
            User.utm_medium.label("utm_medium"),
            User.utm_campaign.label("utm_campaign"),
            cast(null(), String(100)).label("utm_content"),
            cast(null(), String(100)).label("utm_term"),
        )
        .join(User, User.id == CreditPurchase.user_id)
        .where(paid_state == "paid", CreditPurchase.paid_at.is_not(None))
    )
    conversions = union_all(analytics_rows, purchase_rows).subquery("marketing_conversions")
    statement = select(conversions)
    if boundary is not None:
        boundary_time, boundary_id = boundary
        statement = statement.where(
            or_(
                conversions.c.occurred_at < boundary_time,
                and_(conversions.c.occurred_at == boundary_time, conversions.c.event_id < boundary_id),
            )
        )
    statement = statement.order_by(conversions.c.occurred_at.desc(), conversions.c.event_id.desc()).limit(limit + 1)
    rows = (await db.execute(statement)).mappings().all()
    items = [
        MarketingConversion(
            event_id=row["event_id"],
            event_type=row["event_type"],
            occurred_at=_as_utc(row["occurred_at"]),
            customer_ref=pseudonymous_customer_ref(row["customer_id"]),
            amount=round(row["amount_cents"] / 100, 2) if row["amount_cents"] is not None else None,
            currency=row["currency"],
            attribution=_attribution(
                acquisition_source=row["acquisition_source"],
                utm_source=row["utm_source"],
                utm_medium=row["utm_medium"],
                utm_campaign=row["utm_campaign"],
                utm_content=row["utm_content"],
                utm_term=row["utm_term"],
            ),
        )
        for row in rows
    ]
    page_items = items[:limit]
    next_cursor = _encode_cursor(page_items[-1]) if len(items) > limit and page_items else None
    return MarketingConversionPage(items=page_items, next_cursor=next_cursor)
