import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.config import settings
from app.db.models import AnalyticsEvent


def _event(
    *,
    event_id: str | None = None,
    event_name: str = "landing_viewed",
    occurred_at: str | None = None,
    anonymous_session_id: str | None = None,
    page: str = "landing",
    device_class: str = "desktop",
    properties: dict | None = None,
    **extra,
) -> dict:
    payload = {
        "event_id": event_id or str(uuid.uuid4()),
        "event_name": event_name,
        "schema_version": 1,
        "occurred_at": occurred_at or datetime.now(timezone.utc).isoformat(),
        "anonymous_session_id": anonymous_session_id or str(uuid.uuid4()),
        "page": page,
        "device_class": device_class,
        "properties": properties or {"landing_variant": "control", "niche": None},
    }
    payload.update(extra)
    return payload


VALID_CLIENT_EVENTS = [
    ("landing_viewed", "landing", {"landing_variant": "control", "niche": "curiosidades"}),
    (
        "hero_cta_clicked",
        "landing",
        {"placement": "hero", "cta_variant": "control", "selected_package": "starter"},
    ),
    (
        "example_played",
        "examples",
        {
            "example_id": "o-fato-historico-que-quase-ninguem-conhece",
            "niche": "curiosidades",
            "placement": "examples",
        },
    ),
    (
        "example_completed",
        "viewer",
        {"example_id": "o-fato-historico-que-quase-ninguem-conhece", "completion_bucket": 100},
    ),
    ("pricing_viewed", "credits", {"placement": "credits", "pricing_variant": "control"}),
    (
        "pricing_package_selected",
        "credits",
        {"package": "popular", "placement": "credits"},
    ),
    ("support_opened", "support", {"placement": "faq", "reason_code": "payment"}),
    (
        "signup_started",
        "auth_register",
        {"selected_package": "professional", "source_page": "landing"},
    ),
    (
        "credits_viewed",
        "dashboard",
        {"balance_bucket": "medium", "placement": "dashboard"},
    ),
    (
        "credits_low",
        "editor",
        {"balance_bucket": "low", "required_bucket": "dialogue", "placement": "editor"},
    ),
    (
        "user_returned",
        "dashboard",
        {"entry": "direct", "days_since_last_value_bucket": "8_30"},
    ),
    (
        "referral_shared",
        "credits",
        {"channel": "whatsapp", "placement": "after_export"},
    ),
    ("feedback_submitted", "editor", {"score": 5, "context": "first_export"}),
    (
        "onboarding_step_viewed",
        "dashboard",
        {"step": "first_video", "entry": "direct"},
    ),
    (
        "editor_opened",
        "editor",
        {"entry": "generation_complete"},
    ),
]


@pytest.mark.asyncio
async def test_analytics_flag_off_accepts_nothing_and_writes_no_rows(
    client,
    db_session,
    monkeypatch,
):
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", False)

    response = await client.post("/api/v1/analytics/events", json={"events": [_event()]})

    assert response.status_code == 202
    assert response.json() == {"accepted": 0, "duplicates": 0, "enabled": False}
    assert await db_session.scalar(select(func.count()).select_from(AnalyticsEvent)) == 0


@pytest.mark.asyncio
async def test_analytics_accepts_twenty_strict_events_and_derives_storage_fields(
    client,
    db_session,
    monkeypatch,
):
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)
    session_id = str(uuid.uuid4())
    events = [
        _event(
            anonymous_session_id=session_id,
            utm_source="youtube",
            utm_medium="paid_social",
            utm_campaign="launch_2026",
        )
        for _ in range(20)
    ]

    response = await client.post("/api/v1/analytics/events", json={"events": events})

    assert response.status_code == 202
    assert response.json() == {"accepted": 20, "duplicates": 0, "enabled": True}
    rows = list((await db_session.scalars(select(AnalyticsEvent))).all())
    assert len(rows) == 20
    assert all(row.authority == "client" for row in rows)
    assert all(row.user_id is None for row in rows)
    assert all(row.acquisition_source == "paid" for row in rows)
    assert all(row.utm_source == "youtube" for row in rows)
    assert all(row.payload_hash and len(row.payload_hash) == 64 for row in rows)


@pytest.mark.asyncio
async def test_analytics_accepts_the_complete_client_event_catalog(
    client,
    db_session,
    monkeypatch,
):
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)
    events = [
        _event(event_name=event_name, page=page, properties=properties)
        for event_name, page, properties in VALID_CLIENT_EVENTS
    ]

    response = await client.post("/api/v1/analytics/events", json={"events": events})

    assert response.status_code == 202
    assert response.json() == {"accepted": 15, "duplicates": 0, "enabled": True}
    stored_names = set(await db_session.scalars(select(AnalyticsEvent.event_name)))
    assert stored_names == {event_name for event_name, _, _ in VALID_CLIENT_EVENTS}


@pytest.mark.asyncio
async def test_analytics_rejects_oversized_batch_and_raw_body(client, monkeypatch):
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)
    too_many = await client.post(
        "/api/v1/analytics/events",
        json={"events": [_event() for _ in range(21)]},
    )
    assert too_many.status_code == 413

    oversized = json.dumps({"events": [_event(padding="x" * 66_000)]}).encode()
    raw = await client.post(
        "/api/v1/analytics/events",
        content=oversized,
        headers={"Content-Type": "application/json"},
    )
    assert raw.status_code == 413


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation",
    [
        lambda event: event.update(event_name="unknown_event"),
        lambda event: event.update(user_id=str(uuid.uuid4())),
        lambda event: event.update(authority="server"),
        lambda event: event.update(email="pii@example.com"),
        lambda event: event["properties"].update(comment="free form PII"),
        lambda event: event.update(page="https://clipia.com.br/?email=pii@example.com"),
    ],
)
async def test_analytics_rejects_unknown_extra_pii_and_server_only_fields(
    client,
    monkeypatch,
    mutation,
):
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)
    event = _event()
    mutation(event)

    response = await client.post("/api/v1/analytics/events", json={"events": [event]})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_analytics_optional_auth_rejects_invalid_and_derives_valid_user(
    client,
    db_session,
    monkeypatch,
    verified_user,
    auth_headers,
):
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)
    invalid = await client.post(
        "/api/v1/analytics/events",
        headers={"Authorization": "Bearer invalid-token"},
        json={"events": [_event()]},
    )
    assert invalid.status_code == 401

    event = _event()
    valid = await client.post(
        "/api/v1/analytics/events",
        headers=auth_headers(verified_user),
        json={"events": [event]},
    )
    assert valid.status_code == 202
    stored = await db_session.get(AnalyticsEvent, uuid.UUID(event["event_id"]))
    assert stored is not None
    assert stored.user_id == verified_user.id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "event",
    [
        _event(event_id=str(uuid.uuid1())),
        _event(anonymous_session_id=str(uuid.uuid1())),
        _event(occurred_at=datetime.now().isoformat()),
        _event(occurred_at=(datetime.now(timezone.utc) + timedelta(minutes=6)).isoformat()),
        _event(occurred_at=(datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()),
    ],
)
async def test_analytics_rejects_non_v4_ids_and_out_of_window_timestamps(
    client,
    monkeypatch,
    event,
):
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)

    response = await client.post("/api/v1/analytics/events", json={"events": [event]})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_analytics_replay_conflict_and_duplicate_inside_batch(
    client,
    db_session,
    monkeypatch,
):
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)
    event = _event()

    first = await client.post("/api/v1/analytics/events", json={"events": [event]})
    replay = await client.post("/api/v1/analytics/events", json={"events": [event]})
    changed = {**event, "device_class": "mobile"}
    conflict = await client.post("/api/v1/analytics/events", json={"events": [changed]})
    duplicate_batch = await client.post(
        "/api/v1/analytics/events",
        json={"events": [event, event]},
    )

    assert first.json() == {"accepted": 1, "duplicates": 0, "enabled": True}
    assert replay.json() == {"accepted": 0, "duplicates": 1, "enabled": True}
    assert conflict.status_code == 409
    assert duplicate_batch.status_code == 422
    assert await db_session.scalar(select(func.count()).select_from(AnalyticsEvent)) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "event",
    [
        _event(
            event_name="example_played",
            page="examples",
            properties={"example_id": "not-in-catalog", "niche": "curiosidades", "placement": "examples"},
        ),
        _event(
            event_name="pricing_package_selected",
            properties={"package": "pro", "placement": "landing"},
        ),
        _event(properties={"landing_variant": "control", "niche": "unknown"}),
    ],
)
async def test_analytics_rejects_unknown_catalog_ids_niches_and_packages(
    client,
    monkeypatch,
    event,
):
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)

    response = await client.post("/api/v1/analytics/events", json={"events": [event]})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_analytics_rate_limit_uses_observed_ip_without_persisting_it(
    client,
    db_session,
    monkeypatch,
):
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)
    headers = {"CF-Connecting-IP": "198.51.100.77"}
    responses = [
        await client.post(
            "/api/v1/analytics/events",
            headers=headers,
            json={"events": [_event()]},
        )
        for _ in range(31)
    ]

    assert [response.status_code for response in responses[:30]] == [202] * 30
    assert responses[30].status_code == 429
    rows = list((await db_session.scalars(select(AnalyticsEvent))).all())
    assert len(rows) == 30
    assert not any(
        "ip" in column.name.lower() or "agent" in column.name.lower() for column in AnalyticsEvent.__table__.columns
    )
