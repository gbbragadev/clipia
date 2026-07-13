from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.analytics.service import append_server_event
from app.config import settings
from app.db.models import AnalyticsEvent

SERVER_EVENTS = [
    ("user_registered", {"selected_package": "starter", "niche": "curiosidades"}),
    ("email_verified", {"welcome_credits": 2}),
    (
        "generation_requested",
        {"operation_kind": "generation", "credit_cost": 1, "generation_ordinal": "first"},
    ),
    (
        "generation_completed",
        {"operation_kind": "generation", "generation_ordinal": "first"},
    ),
    (
        "generation_failed",
        {"operation_kind": "generation", "generation_ordinal": "first", "reason_code": "provider"},
    ),
    ("video_exported", {"export_ordinal": "first"}),
    (
        "checkout_started",
        {"provider": "stripe", "package": "popular", "total_credits": 35},
    ),
    (
        "payment_completed",
        {"provider": "stripe", "package": "popular", "total_credits": 35},
    ),
    ("credit_balance_changed", {"reason": "purchase", "delta": 35}),
    ("second_generation_requested", {"credit_cost": 1}),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("event_name", "properties"), SERVER_EVENTS)
async def test_server_event_catalog_is_typed_append_only_and_idempotent(
    db_session,
    verified_user,
    monkeypatch,
    event_name,
    properties,
):
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)
    occurred_at = datetime.now(timezone.utc)

    inserted = await append_server_event(
        db_session,
        event_name=event_name,
        user=verified_user,
        properties=properties,
        idempotency_key=f"test:{event_name}",
        occurred_at=occurred_at,
    )
    duplicate = await append_server_event(
        db_session,
        event_name=event_name,
        user=verified_user,
        properties=properties,
        idempotency_key=f"test:{event_name}",
        occurred_at=occurred_at,
    )
    await db_session.commit()

    assert inserted is True
    assert duplicate is False
    row = await db_session.scalar(select(AnalyticsEvent).where(AnalyticsEvent.event_name == event_name))
    assert row is not None
    assert row.authority == "server"
    assert row.user_id == verified_user.id
    assert row.device_class == "unknown"
    assert row.properties == properties
    assert len(row.payload_hash) == 64


@pytest.mark.asyncio
async def test_server_events_derive_acquisition_without_pii(db_session, verified_user, monkeypatch):
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)
    verified_user.utm_source = "youtube"
    verified_user.utm_medium = "paid_social"
    verified_user.utm_campaign = "nicho-curiosidades"
    await db_session.merge(verified_user)

    await append_server_event(
        db_session,
        event_name="user_registered",
        user=verified_user,
        properties={"selected_package": None, "niche": "curiosidades"},
        idempotency_key="registration:acquisition",
        occurred_at=datetime.now(timezone.utc),
    )
    await db_session.commit()

    row = await db_session.scalar(select(AnalyticsEvent))
    assert row is not None
    assert row.acquisition_source == "paid"
    assert row.utm_source == "youtube"
    assert "email" not in row.properties
    assert "name" not in row.properties


@pytest.mark.asyncio
async def test_server_event_flag_off_writes_nothing(db_session, verified_user, monkeypatch):
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", False)

    inserted = await append_server_event(
        db_session,
        event_name="email_verified",
        user=verified_user,
        properties={"welcome_credits": 2},
        idempotency_key="verification:disabled",
        occurred_at=datetime.now(timezone.utc),
    )

    assert inserted is False
    assert await db_session.scalar(select(func.count()).select_from(AnalyticsEvent)) == 0


@pytest.mark.asyncio
async def test_server_event_rejects_unknown_or_untyped_properties(db_session, verified_user):
    with pytest.raises(ValidationError):
        await append_server_event(
            db_session,
            event_name="payment_completed",
            user=verified_user,
            properties={"provider": "stripe", "package": "popular", "total_credits": 35, "email": "pii@example.com"},
            idempotency_key="invalid:extra",
            occurred_at=datetime.now(timezone.utc),
        )

    with pytest.raises(ValueError, match="Unsupported server analytics event"):
        await append_server_event(
            db_session,
            event_name="invented_event",
            user=verified_user,
            properties={},
            idempotency_key="invalid:name",
            occurred_at=datetime.now(timezone.utc),
        )
