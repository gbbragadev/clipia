from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import update

from app.config import settings
from app.db.models import AnalyticsEvent, CreditPurchase, User

pytestmark = pytest.mark.asyncio


def _server_event(*, user_id, event_name: str, occurred_at: datetime, source: str = "paid") -> AnalyticsEvent:
    return AnalyticsEvent(
        event_id=uuid.uuid4(),
        event_name=event_name,
        schema_version=1,
        authority="server",
        occurred_at=occurred_at,
        anonymous_session_id=None,
        user_id=user_id,
        page="auth_register",
        acquisition_source=source,
        utm_source="meta",
        utm_medium="paid_social",
        utm_campaign="creator_launch",
        utm_content=None,
        utm_term=None,
        device_class="unknown",
        properties={},
        payload_hash="a" * 64,
    )


def _marketing_headers() -> dict[str, str]:
    return {"X-Marketing-Token": "marketing-token-value"}


async def test_marketing_export_requires_configured_constant_time_token(client, monkeypatch):
    monkeypatch.setattr(settings, "MARKETING_EXPORT_TOKEN", "marketing-token-value", raising=False)
    monkeypatch.setattr(settings, "MARKETING_PSEUDONYM_SECRET", "pseudonym-secret-value", raising=False)

    path = "/api/v1/internal/marketing/summary?from=2026-07-01&to=2026-07-02"
    absent = await client.get(path)
    wrong = await client.get(path, headers={"X-Marketing-Token": "wrong-token"})
    valid = await client.get(path, headers={"X-Marketing-Token": "marketing-token-value"})

    assert absent.status_code == 401
    assert wrong.status_code == 401
    assert valid.status_code == 200


async def test_marketing_summary_rejects_reversed_oversized_and_future_ranges(client, monkeypatch):
    monkeypatch.setattr(settings, "MARKETING_EXPORT_TOKEN", "marketing-token-value")
    monkeypatch.setattr(settings, "MARKETING_PSEUDONYM_SECRET", "pseudonym-secret-value")
    headers = {"X-Marketing-Token": "marketing-token-value"}

    reversed_range = await client.get(
        "/api/v1/internal/marketing/summary?from=2026-07-10&to=2026-07-01", headers=headers
    )
    oversized_range = await client.get(
        "/api/v1/internal/marketing/summary?from=2026-01-01&to=2026-07-01", headers=headers
    )
    future_range = await client.get("/api/v1/internal/marketing/summary?from=2026-07-17&to=2026-07-18", headers=headers)

    assert reversed_range.status_code == 422
    assert oversized_range.status_code == 422
    assert future_range.status_code == 422


async def test_marketing_summary_uses_first_party_events_and_only_paid_purchases(
    client, db_session, verified_user, monkeypatch
):
    monkeypatch.setattr(settings, "MARKETING_EXPORT_TOKEN", "marketing-token-value")
    monkeypatch.setattr(settings, "MARKETING_PSEUDONYM_SECRET", "pseudonym-secret-value")
    occurred_at = datetime(2026, 7, 10, 12, tzinfo=timezone.utc)
    db_session.add_all(
        [
            _server_event(user_id=verified_user.id, event_name="email_verified", occurred_at=occurred_at),
            CreditPurchase(
                user_id=verified_user.id,
                package_name="starter",
                credits_amount=20,
                bonus_credits=0,
                price_brl=1234,
                provider="stripe",
                status="approved",
                payment_state="paid",
                currency="BRL",
                paid_at=occurred_at,
            ),
            CreditPurchase(
                user_id=verified_user.id,
                package_name="starter",
                credits_amount=20,
                bonus_credits=0,
                price_brl=9999,
                provider="stripe",
                status="pending",
                payment_state="pending",
                currency="BRL",
                created_at=occurred_at,
            ),
        ]
    )
    await db_session.commit()

    response = await client.get(
        "/api/v1/internal/marketing/summary?from=2026-07-01&to=2026-07-16",
        headers=_marketing_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["funnel"] == [{"event_type": "email_verified", "count": 1}]
    assert body["sources"] == [{"acquisition_source": "paid", "count": 1}]
    assert body["revenue"] == {"approved_purchases": 1, "gross_amount": 12.34, "currency": "BRL"}


async def test_marketing_conversions_are_cursor_paginated_stable_and_recursively_pii_free(
    client, db_session, verified_user, monkeypatch
):
    monkeypatch.setattr(settings, "MARKETING_EXPORT_TOKEN", "marketing-token-value")
    monkeypatch.setattr(settings, "MARKETING_PSEUDONYM_SECRET", "pseudonym-secret-value")
    # Historical rows may predate stricter attribution validation. The export
    # must fail closed instead of reflecting email/path/secret-like values.
    verified_user.utm_source = "victim@example.com"
    verified_user.utm_medium = "C:\\private\\secret-token"
    verified_user.utm_campaign = "creator_launch"
    await db_session.execute(
        update(User)
        .where(User.id == verified_user.id)
        .values(
            utm_source=verified_user.utm_source,
            utm_medium=verified_user.utm_medium,
            utm_campaign=verified_user.utm_campaign,
        )
    )
    event = _server_event(
        user_id=verified_user.id,
        event_name="email_verified",
        occurred_at=datetime(2026, 7, 10, 12, tzinfo=timezone.utc),
    )
    purchase = CreditPurchase(
        user_id=verified_user.id,
        package_name="starter",
        credits_amount=20,
        bonus_credits=0,
        price_brl=1234,
        provider="stripe",
        status="approved",
        payment_state="paid",
        currency="BRL",
        paid_at=datetime(2026, 7, 11, 12, tzinfo=timezone.utc),
    )
    db_session.add_all([event, purchase])
    await db_session.commit()

    first = await client.get(
        "/api/v1/internal/marketing/conversions?limit=1",
        headers=_marketing_headers(),
    )
    assert first.status_code == 200
    first_body = first.json()
    assert len(first_body["items"]) == 1
    assert first_body["next_cursor"]

    second = await client.get(
        f"/api/v1/internal/marketing/conversions?limit=1&cursor={first_body['next_cursor']}",
        headers=_marketing_headers(),
    )
    repeated = await client.get(
        "/api/v1/internal/marketing/conversions?limit=2",
        headers=_marketing_headers(),
    )
    assert second.status_code == 200
    assert repeated.status_code == 200
    all_items = first_body["items"] + second.json()["items"]
    assert {item["event_type"] for item in all_items} == {"email_verified", "Purchase"}
    assert all_items[0]["customer_ref"] == repeated.json()["items"][0]["customer_ref"]
    assert len(all_items[0]["customer_ref"]) == 64

    serialized = json.dumps({"first": first_body, "second": second.json()}, sort_keys=True).lower()
    for forbidden in (
        verified_user.email.lower(),
        verified_user.name.lower(),
        "127.0.0.1",
        "c:\\\\",
        "marketing-token-value",
        "pseudonym-secret-value",
        "victim@example.com",
        "c:\\private\\secret-token",
    ):
        assert forbidden not in serialized
    for item in all_items:
        assert set(item) == {
            "event_id",
            "event_type",
            "occurred_at",
            "customer_ref",
            "amount",
            "currency",
            "attribution",
        }
