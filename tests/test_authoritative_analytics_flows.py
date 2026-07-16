from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.auth.referrals import award_verified_referral
from app.config import settings
from app.db.models import AcquisitionReward, AnalyticsEvent, Job, MarketingOffer, ReferralCreditAward, User
from app.payments.checkout_outbox import create_or_resume_checkout
from app.payments.service import _apply_payment_event
from app.services import job_operations


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


async def test_admin_adjustment_appends_credit_event_in_the_adjustment_transaction(
    client,
    db_session,
    admin_user,
    verified_user,
    auth_headers,
    monkeypatch,
):
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)

    response = await client.post(
        f"/api/v1/admin/users/{verified_user.id}/adjust-credits",
        json={"delta": 18, "reason": "beta_invite_2026"},
        headers=auth_headers(admin_user),
    )

    assert response.status_code == 200
    event = await db_session.scalar(
        select(AnalyticsEvent).where(
            AnalyticsEvent.user_id == verified_user.id,
            AnalyticsEvent.event_name == "credit_balance_changed",
        )
    )
    assert event is not None
    assert event.properties == {"reason": "admin", "delta": 18}


async def test_activated_referral_appends_authoritative_referrer_credit_event(
    client,
    db_session,
    verified_user,
    monkeypatch,
):
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)
    referrer_id = verified_user.id
    initial_balance = verified_user.credits
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "referred-analytics@example.com",
            "name": "Referred Analytics",
            "password": "Secret123",
            "consent": True,
            "referral_code": verified_user.referral_code,
        },
    )
    assert response.status_code == 201
    referred = await db_session.scalar(select(User).where(User.email == "referred-analytics@example.com"))
    assert referred is not None and referred.verification_code is not None
    referred_id = referred.id

    verified = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": referred.email, "code": referred.verification_code},
    )

    assert verified.status_code == 200
    assert (
        await db_session.scalar(
            select(AnalyticsEvent).where(
                AnalyticsEvent.user_id == referrer_id,
                AnalyticsEvent.event_name == "credit_balance_changed",
            )
        )
        is None
    )
    db_session.expire_all()
    completed_job = Job(
        user_id=referred_id,
        topic="Referral analytics activation",
        style="educational",
        duration_target=30,
        status="finalizing",
    )
    db_session.add(completed_job)
    await db_session.commit()
    assert (
        await job_operations.finalize_generation(
            db_session,
            completed_job.id,
            script={},
            video_url=f"/storage/output/{completed_job.id}.mp4",
            telemetry={},
        )
        == "finalized"
    )
    await db_session.commit()

    event = await db_session.scalar(
        select(AnalyticsEvent).where(
            AnalyticsEvent.user_id == referrer_id,
            AnalyticsEvent.event_name == "credit_balance_changed",
        )
    )
    assert event is not None
    assert event.properties == {"reason": "referral_activation", "delta": 18}
    reward = await db_session.scalar(select(AcquisitionReward).where(AcquisitionReward.user_id == referrer_id))
    assert reward is not None
    assert reward.reward_type == "referral_activation"
    assert reward.source_user_id == referred_id
    db_session.expire_all()
    assert (await db_session.get(User, referrer_id)).credits == initial_balance + 18
    assert await db_session.scalar(select(func.count()).select_from(ReferralCreditAward)) == 0


async def test_retired_verification_referral_hook_creates_no_new_historical_awards(
    db_session,
    verified_user,
):
    referrer_id = verified_user.id
    initial_balance = verified_user.credits
    referred_users = [
        User(
            email=f"referral-limit-{index}@example.com",
            name=f"Referral {index}",
            password_hash="hashed",
            credits=2,
            email_verified=True,
            referral_code=uuid.uuid4().hex[:8],
            referred_by=verified_user.id,
        )
        for index in range(11)
    ]
    db_session.add_all(referred_users)
    await db_session.commit()

    applied = []
    for referred in referred_users:
        applied.append(await award_verified_referral(db_session, referred))
        await db_session.commit()

    assert applied == [0] * 11
    assert await award_verified_referral(db_session, referred_users[0]) == 0
    assert await db_session.scalar(select(func.count()).select_from(ReferralCreditAward)) == 0
    db_session.expire_all()
    assert (await db_session.get(User, referrer_id)).credits == initial_balance


async def test_campaign_reward_failure_rolls_back_email_verification(
    client,
    db_session,
    monkeypatch,
):
    offer = MarketingOffer(code="creator20_v1", bonus_credits=18, is_active=True)
    db_session.add(offer)
    await db_session.commit()
    registered = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "referral-rollback@example.com",
            "name": "Campaign Rollback",
            "password": "Secret123",
            "consent": True,
            "offer_code": offer.code,
        },
    )
    assert registered.status_code == 201
    referred = await db_session.scalar(select(User).where(User.email == "referral-rollback@example.com"))
    assert referred is not None and referred.verification_code is not None
    referred_id = referred.id
    code = referred.verification_code

    async def fail_award(*_args, **_kwargs):
        raise RuntimeError("campaign reward persistence failed")

    monkeypatch.setattr("app.auth.routes.claim_campaign_reward", fail_award)
    response = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": referred.email, "code": code},
    )
    assert response.status_code == 500

    db_session.expire_all()
    persisted_referred = await db_session.get(User, referred_id)
    reward = await db_session.scalar(select(AcquisitionReward).where(AcquisitionReward.user_id == referred_id))
    assert persisted_referred is not None and persisted_referred.email_verified is False
    assert persisted_referred.credits == 0
    assert persisted_referred.verification_code == code
    assert reward is None
