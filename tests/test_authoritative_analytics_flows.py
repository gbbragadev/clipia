from __future__ import annotations

from sqlalchemy import func, select

from app.config import settings
from app.db.models import AnalyticsEvent, Job, User
from app.payments.checkout_outbox import create_or_resume_checkout
from app.payments.service import _apply_payment_event


def _generate_payload(topic: str) -> dict:
    return {
        "topic": topic,
        "style": "educational",
        "duration_target": 30,
        "template_id": "stock_narration",
    }


async def _event_names(db_session, user_id) -> list[str]:
    return list(
        await db_session.scalars(
            select(AnalyticsEvent.event_name)
            .where(AnalyticsEvent.user_id == user_id)
            .order_by(AnalyticsEvent.received_at, AnalyticsEvent.event_name)
        )
    )


async def test_registration_and_verification_append_authoritative_events_once(
    client,
    db_session,
    monkeypatch,
):
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "analytics-flow@example.com",
            "name": "Analytics Flow",
            "password": "Secret123",
            "consent": True,
            "selected_package": "professional",
            "utm_source": "youtube",
            "utm_medium": "paid_social",
            "utm_campaign": "nicho-curiosidades",
        },
    )
    assert response.status_code == 201

    user = await db_session.scalar(select(User).where(User.email == "analytics-flow@example.com"))
    assert user is not None and user.verification_code is not None
    user_id = user.id
    verified = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": user.email, "code": user.verification_code},
    )
    assert verified.status_code == 200
    replay = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": user.email, "code": user.verification_code},
    )
    assert replay.status_code == 200
    assert replay.json() == {"status": "already_verified"}

    db_session.expire_all()
    names = await _event_names(db_session, user_id)
    assert names.count("user_registered") == 1
    assert names.count("email_verified") == 1
    assert names.count("credit_balance_changed") == 1
    registered = await db_session.scalar(select(AnalyticsEvent).where(AnalyticsEvent.event_name == "user_registered"))
    assert registered is not None
    assert registered.properties == {"selected_package": "professional", "niche": "curiosidades"}
    assert registered.acquisition_source == "paid"


async def test_generation_second_generation_and_export_are_authoritative_and_idempotent(
    client,
    db_session,
    verified_user,
    auth_headers,
    storage_dir,
    monkeypatch,
):
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)
    headers = auth_headers(verified_user)
    first = await client.post(
        "/api/v1/generate",
        headers=headers,
        json=_generate_payload("Primeiro tema para analytics autoritativo"),
    )
    second = await client.post(
        "/api/v1/generate",
        headers=headers,
        json=_generate_payload("Segundo tema para analytics autoritativo"),
    )
    assert [first.status_code, second.status_code] == [202, 202]

    job_id = first.json()["job_id"]
    output = storage_dir / "output" / f"{job_id}.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(b"video")
    first_export = await client.get(f"/api/v1/jobs/{job_id}/download", headers=headers)
    repeated_export = await client.get(f"/api/v1/jobs/{job_id}/download", headers=headers)
    assert [first_export.status_code, repeated_export.status_code] == [200, 200]

    db_session.expire_all()
    names = await _event_names(db_session, verified_user.id)
    assert names.count("generation_requested") == 2
    assert names.count("second_generation_requested") == 1
    assert names.count("video_exported") == 1
    assert names.count("credit_balance_changed") == 2
    second_event = await db_session.scalar(
        select(AnalyticsEvent).where(AnalyticsEvent.event_name == "second_generation_requested")
    )
    assert second_event is not None and second_event.properties == {"credit_cost": 1}
    exported_job = await db_session.get(Job, job_id)
    assert exported_job is not None and exported_job.exported_at is not None


async def test_checkout_and_payment_append_frozen_financial_events(
    db_session,
    verified_user,
    monkeypatch,
):
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)
    checkout = await create_or_resume_checkout(
        verified_user,
        "professional",
        "stripe",
        db_session,
        attempt_inline=False,
    )
    applied = await _apply_payment_event(
        db_session,
        purchase_id=checkout.purchase_id,
        provider="stripe",
        event_key="evt_authoritative_paid",
        event_type="checkout.session.completed",
        transition="paid",
        external_payment_id="pi_authoritative_paid",
        external_checkout_id=None,
        validate=lambda _purchase: True,
    )
    replay = await _apply_payment_event(
        db_session,
        purchase_id=checkout.purchase_id,
        provider="stripe",
        event_key="evt_authoritative_paid",
        event_type="checkout.session.completed",
        transition="paid",
        external_payment_id="pi_authoritative_paid",
        external_checkout_id=None,
        validate=lambda _purchase: True,
    )
    assert applied.applied is True and applied.balance_delta == 100
    assert replay.applied is False

    db_session.expire_all()
    rows = list(
        await db_session.scalars(
            select(AnalyticsEvent).where(AnalyticsEvent.user_id == verified_user.id).order_by(AnalyticsEvent.event_name)
        )
    )
    assert [row.event_name for row in rows] == [
        "checkout_started",
        "credit_balance_changed",
        "payment_completed",
    ]
    for row in rows:
        if row.event_name in {"checkout_started", "payment_completed"}:
            assert row.properties == {
                "provider": "stripe",
                "package": "professional",
                "total_credits": 100,
            }
    assert await db_session.scalar(select(func.count()).select_from(AnalyticsEvent)) == 3
