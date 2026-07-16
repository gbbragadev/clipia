from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import get_type_hints

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from pydantic import SecretStr
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import AnalyticsEvent, CreditPurchase, User
from app.marketing.export import _encode_cursor
from app.marketing.routes import marketing_conversions, marketing_summary, require_marketing_token
from app.marketing.schemas import Attribution, MarketingConversion, MarketingConversionPage, MarketingSummary

pytestmark = pytest.mark.asyncio


def _server_event(
    *, user_id: uuid.UUID, event_name: str, occurred_at: datetime, source: str = "paid"
) -> AnalyticsEvent:
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


async def test_marketing_export_requires_configured_constant_time_token(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "MARKETING_EXPORT_TOKEN", SecretStr("marketing-token-value"), raising=False)
    monkeypatch.setattr(settings, "MARKETING_PSEUDONYM_SECRET", SecretStr("pseudonym-secret-value"), raising=False)

    path = "/api/v1/internal/marketing/summary?from=2026-07-01&to=2026-07-02"
    absent = await client.get(path)
    wrong = await client.get(path, headers={"X-Marketing-Token": "wrong-token"})
    valid = await client.get(path, headers={"X-Marketing-Token": "marketing-token-value"})

    assert absent.status_code == 401
    assert wrong.status_code == 401
    assert valid.status_code == 200


async def test_marketing_token_rejects_non_ascii_without_compare_digest_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "MARKETING_EXPORT_TOKEN", SecretStr("marketing-token-value"))

    with pytest.raises(HTTPException) as exc_info:
        require_marketing_token("não-ascii")

    assert exc_info.value.status_code == 401


async def test_marketing_routes_declare_response_return_annotations() -> None:
    assert get_type_hints(marketing_summary)["return"] is MarketingSummary
    assert get_type_hints(marketing_conversions)["return"] is MarketingConversionPage


async def test_marketing_summary_rejects_reversed_oversized_and_future_ranges(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "MARKETING_EXPORT_TOKEN", SecretStr("marketing-token-value"))
    monkeypatch.setattr(settings, "MARKETING_PSEUDONYM_SECRET", SecretStr("pseudonym-secret-value"))
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


async def test_marketing_summary_allows_exactly_ninety_inclusive_utc_dates(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "MARKETING_EXPORT_TOKEN", SecretStr("marketing-token-value"))
    monkeypatch.setattr(settings, "MARKETING_PSEUDONYM_SECRET", SecretStr("pseudonym-secret-value"))
    today_utc = datetime.now(timezone.utc).date()
    headers = _marketing_headers()

    exact_ninety = await client.get(
        "/api/v1/internal/marketing/summary",
        params={"from": (today_utc - timedelta(days=89)).isoformat(), "to": today_utc.isoformat()},
        headers=headers,
    )
    ninety_one = await client.get(
        "/api/v1/internal/marketing/summary",
        params={"from": (today_utc - timedelta(days=90)).isoformat(), "to": today_utc.isoformat()},
        headers=headers,
    )

    assert exact_ninety.status_code == 200
    assert ninety_one.status_code == 422


async def test_marketing_summary_uses_first_party_events_and_only_paid_purchases(
    client: AsyncClient,
    db_session: AsyncSession,
    verified_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "MARKETING_EXPORT_TOKEN", SecretStr("marketing-token-value"))
    monkeypatch.setattr(settings, "MARKETING_PSEUDONYM_SECRET", SecretStr("pseudonym-secret-value"))
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
    client: AsyncClient,
    db_session: AsyncSession,
    verified_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "MARKETING_EXPORT_TOKEN", SecretStr("marketing-token-value"))
    monkeypatch.setattr(settings, "MARKETING_PSEUDONYM_SECRET", SecretStr("pseudonym-secret-value"))
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


async def test_marketing_attribution_exports_only_explicit_field_allowlists(
    client: AsyncClient,
    db_session: AsyncSession,
    verified_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "MARKETING_EXPORT_TOKEN", SecretStr("marketing-token-value"))
    monkeypatch.setattr(settings, "MARKETING_PSEUDONYM_SECRET", SecretStr("pseudonym-secret-value"))
    occurred_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    allowed = _server_event(user_id=verified_user.id, event_name="email_verified", occurred_at=occurred_at)
    allowed.event_id = uuid.UUID("10000000-0000-4000-8000-000000000001")
    allowed.utm_source = "meta"
    allowed.utm_medium = "paid_social"
    allowed.utm_campaign = "clipia_creator20_pilot"
    allowed.utm_content = "share"
    allowed.utm_term = None
    arbitrary_values = (
        "alice",
        "alice.smith",
        "52998224725",
        "5545999999999",
        "sk_live_123456",
        "ghp_abcdef123456",
        "c-private-users-alice",
    )
    arbitrary_events = []
    for index, value in enumerate(arbitrary_values, start=2):
        event = _server_event(user_id=verified_user.id, event_name="email_verified", occurred_at=occurred_at)
        event.event_id = uuid.UUID(f"10000000-0000-4000-8000-{index:012d}")
        event.utm_source = value
        event.utm_medium = value
        event.utm_campaign = value
        event.utm_content = value
        event.utm_term = value
        arbitrary_events.append(event)
    db_session.add_all([allowed, *arbitrary_events])
    await db_session.commit()

    response = await client.get(
        "/api/v1/internal/marketing/conversions?limit=20",
        headers=_marketing_headers(),
    )

    assert response.status_code == 200
    items = response.json()["items"]
    allowed_item = next(item for item in items if item["event_id"].endswith("000000000001"))
    assert allowed_item["attribution"] == {
        "acquisition_source": "paid",
        "utm_source": "meta",
        "utm_medium": "paid_social",
        "utm_campaign": "clipia_creator20_pilot",
        "utm_content": "share",
        "utm_term": None,
    }
    serialized = json.dumps(items, sort_keys=True).lower()
    for forbidden in arbitrary_values:
        assert forbidden not in serialized
    for item in items:
        if item is allowed_item:
            continue
        assert all(value is None for key, value in item["attribution"].items() if key.startswith("utm_"))


async def test_marketing_conversion_keyset_walks_all_global_ties_once(
    client: AsyncClient,
    db_session: AsyncSession,
    verified_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "MARKETING_EXPORT_TOKEN", SecretStr("marketing-token-value"))
    monkeypatch.setattr(settings, "MARKETING_PSEUDONYM_SECRET", SecretStr("pseudonym-secret-value"))
    occurred_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    analytics_ids = [
        uuid.UUID("00000000-0000-4000-8000-000000000001"),
        uuid.UUID("00000000-0000-4000-8000-000000000002"),
        uuid.UUID("ffffffff-ffff-4fff-8fff-fffffffffff1"),
    ]
    purchase_ids = [
        uuid.UUID("00000000-0000-4000-8000-000000000011"),
        uuid.UUID("00000000-0000-4000-8000-000000000012"),
        uuid.UUID("ffffffff-ffff-4fff-8fff-fffffffffff2"),
    ]
    events = []
    for event_id in analytics_ids:
        event = _server_event(user_id=verified_user.id, event_name="email_verified", occurred_at=occurred_at)
        event.event_id = event_id
        events.append(event)
    purchases = [
        CreditPurchase(
            id=purchase_id,
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
        )
        for purchase_id in purchase_ids
    ]
    db_session.add_all([*events, *purchases])
    await db_session.commit()
    expected = {
        *(f"analytics:{event_id}" for event_id in analytics_ids),
        *(f"purchase:{purchase_id}" for purchase_id in purchase_ids),
    }

    cursor = None
    seen = []
    for _page in range(10):
        response = await client.get(
            "/api/v1/internal/marketing/conversions",
            params={"limit": 1, **({"cursor": cursor} if cursor else {})},
            headers=_marketing_headers(),
        )
        assert response.status_code == 200
        body = response.json()
        seen.extend(item["event_id"] for item in body["items"])
        cursor = body["next_cursor"]
        if cursor is None:
            break

    assert len(seen) == len(set(seen))
    assert set(seen) == expected
    assert seen == sorted(seen, reverse=True)


async def test_marketing_cursor_is_signed_and_rejects_tampering_and_extreme_dates(
    client: AsyncClient,
    db_session: AsyncSession,
    verified_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "MARKETING_EXPORT_TOKEN", SecretStr("marketing-token-value"))
    monkeypatch.setattr(settings, "MARKETING_PSEUDONYM_SECRET", SecretStr("pseudonym-secret-value"))
    event = _server_event(
        user_id=verified_user.id,
        event_name="email_verified",
        occurred_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    older = _server_event(
        user_id=verified_user.id,
        event_name="email_verified",
        occurred_at=datetime.now(timezone.utc) - timedelta(minutes=2),
    )
    db_session.add_all([event, older])
    await db_session.commit()
    first = await client.get(
        "/api/v1/internal/marketing/conversions?limit=1",
        headers=_marketing_headers(),
    )
    cursor = first.json()["next_cursor"]
    assert cursor is not None
    assert cursor.count(".") == 1
    payload, signature = cursor.split(".")
    tampered_payload = ("A" if payload[0] != "A" else "B") + payload[1:]
    tampered_signature = ("A" if signature[0] != "A" else "B") + signature[1:]

    bad_payload = await client.get(
        "/api/v1/internal/marketing/conversions",
        params={"cursor": f"{tampered_payload}.{signature}"},
        headers=_marketing_headers(),
    )
    bad_signature = await client.get(
        "/api/v1/internal/marketing/conversions",
        params={"cursor": f"{payload}.{tampered_signature}"},
        headers=_marketing_headers(),
    )
    extreme = MarketingConversion(
        event_id=f"analytics:{uuid.uuid4()}",
        event_type="email_verified",
        occurred_at=datetime(1, 1, 1, tzinfo=timezone.utc),
        customer_ref="a" * 64,
        attribution=Attribution(acquisition_source="direct"),
    )
    extreme_date = await client.get(
        "/api/v1/internal/marketing/conversions",
        params={"cursor": _encode_cursor(extreme)},
        headers=_marketing_headers(),
    )

    assert bad_payload.status_code == 422
    assert bad_signature.status_code == 422
    assert extreme_date.status_code == 422


async def test_marketing_cursor_rejects_signed_noncanonical_event_uuid(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "MARKETING_EXPORT_TOKEN", SecretStr("marketing-token-value"))
    monkeypatch.setattr(settings, "MARKETING_PSEUDONYM_SECRET", SecretStr("pseudonym-secret-value"))
    malformed = MarketingConversion(
        event_id="analytics:00000000-0000-4000-8000-00000000000-",
        event_type="email_verified",
        occurred_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        customer_ref="a" * 64,
        attribution=Attribution(acquisition_source="direct"),
    )

    response = await client.get(
        "/api/v1/internal/marketing/conversions",
        params={"cursor": _encode_cursor(malformed)},
        headers=_marketing_headers(),
    )

    assert response.status_code == 422
