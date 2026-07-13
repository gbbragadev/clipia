import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import update

from app.config import settings
from app.db.models import AnalyticsEvent, CreditPurchase, Job, JobDispatch, User


def _write_file(path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


def _analytics_event(
    event_name: str,
    occurred_at: datetime,
    *,
    session_id=None,
    user_id=None,
    authority: str = "server",
    device_class: str = "unknown",
    properties: dict | None = None,
) -> AnalyticsEvent:
    return AnalyticsEvent(
        event_id=uuid.uuid4(),
        event_name=event_name,
        schema_version=1,
        authority=authority,
        occurred_at=occurred_at,
        received_at=occurred_at,
        anonymous_session_id=session_id,
        user_id=user_id,
        page="landing" if authority == "client" else "dashboard",
        acquisition_source="paid",
        utm_source="youtube",
        utm_medium="paid_social",
        utm_campaign="nicho-curiosidades",
        device_class=device_class,
        properties=properties or {},
        payload_hash=uuid.uuid4().hex * 2,
    )


@pytest.mark.asyncio
async def test_admin_dashboard_requires_admin(client, verified_user, auth_headers):
    response = await client.get("/api/v1/admin/dashboard", headers=auth_headers(verified_user))

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_dashboard_aggregates_finance_funnel_operations_and_recent_activity(
    client,
    db_session,
    verified_user,
    other_verified_user,
    admin_user,
    auth_headers,
    purchase_factory,
    job_factory,
    storage_dir,
):
    approved_purchase = await purchase_factory(status="approved", user_id=verified_user.id)
    pending_purchase = await purchase_factory(status="pending", user_id=other_verified_user.id, package_name="popular")
    old_purchase = await purchase_factory(status="approved", user_id=verified_user.id, package_name="pro")

    queued_job = await job_factory(user_id=verified_user.id, status="queued", pending_credits=1.0)
    processing_job = await job_factory(user_id=verified_user.id, status="processing")
    completed_job = await job_factory(user_id=verified_user.id, status="completed", pending_credits=2.0)
    failed_job = await job_factory(user_id=other_verified_user.id, status="failed")
    old_job = await job_factory(user_id=verified_user.id, status="completed")

    completed_dispatch = JobDispatch(
        job_id=completed_job.id,
        operation_id=completed_job.id,
        kind="generation",
        payload={},
        debited_credits=3,
        state="completed",
    )
    failed_dispatch = JobDispatch(
        job_id=failed_job.id,
        operation_id=failed_job.id,
        kind="generation",
        payload={},
        debited_credits=2,
        state="cancelled",
    )
    queued_dispatch = JobDispatch(
        job_id=queued_job.id,
        operation_id=queued_job.id,
        kind="generation",
        payload={},
        debited_credits=1,
        state="pending",
    )
    processing_dispatch = JobDispatch(
        job_id=processing_job.id,
        operation_id=uuid.uuid4(),
        kind="rerender",
        payload={},
        debited_credits=1,
        state="claimed",
    )
    db_session.add_all([completed_dispatch, failed_dispatch, queued_dispatch, processing_dispatch])

    now = datetime.now(timezone.utc)
    recent_created = now - timedelta(days=2)
    old_created = now - timedelta(days=45)

    await db_session.execute(
        update(User).where(User.id == other_verified_user.id).values(email_verified=False, created_at=recent_created)
    )
    await db_session.execute(update(User).where(User.id == verified_user.id).values(created_at=recent_created))
    await db_session.execute(update(User).where(User.id == admin_user.id).values(created_at=old_created))

    await db_session.execute(
        update(CreditPurchase)
        .where(CreditPurchase.id == approved_purchase.id)
        .values(created_at=recent_created, paid_at=recent_created)
    )
    await db_session.execute(
        update(CreditPurchase).where(CreditPurchase.id == pending_purchase.id).values(created_at=recent_created)
    )
    await db_session.execute(
        update(CreditPurchase)
        .where(CreditPurchase.id == old_purchase.id)
        .values(created_at=old_created, paid_at=old_created)
    )

    await db_session.execute(update(Job).where(Job.id == queued_job.id).values(created_at=recent_created))
    await db_session.execute(update(Job).where(Job.id == processing_job.id).values(created_at=recent_created))
    await db_session.execute(update(Job).where(Job.id == completed_job.id).values(created_at=recent_created))
    await db_session.execute(
        update(Job).where(Job.id == failed_job.id).values(created_at=recent_created, error="ffmpeg failed")
    )
    await db_session.execute(update(Job).where(Job.id == old_job.id).values(created_at=old_created))
    await db_session.commit()

    tracked_job_dir = storage_dir / "jobs" / str(completed_job.id)
    tracked_output = storage_dir / "output" / f"{completed_job.id}.mp4"
    orphan_dir = storage_dir / "jobs" / "orphan-admin-dir"
    _write_file(tracked_job_dir / "asset.bin", 512 * 1024)
    _write_file(tracked_output, 512 * 1024)
    _write_file(orphan_dir / "stale.bin", 256 * 1024)

    response = await client.get("/api/v1/admin/dashboard?range=30d", headers=auth_headers(admin_user))

    assert response.status_code == 200
    body = response.json()

    assert body["range"] == "30d"
    assert body["summary"]["approved_revenue_brl"] == 19.9
    assert body["summary"]["net_revenue_brl"] == 19.9
    assert body["summary"]["pending_revenue_brl"] == 49.9
    assert body["summary"]["approved_orders"] == 1
    assert body["summary"]["pending_orders"] == 1
    assert body["summary"]["average_ticket_brl"] == 19.9
    assert body["summary"]["new_users"] == 2
    assert body["summary"]["verified_users"] == 1
    assert body["summary"]["paying_users"] == 1
    assert body["summary"]["active_jobs"] == 2
    expected_credits_sold = approved_purchase.credits_amount + approved_purchase.bonus_credits
    assert body["summary"]["credits_sold"] == expected_credits_sold
    assert body["summary"]["credits_consumed"] == 3

    assert body["funnel"]["registered"] == 0
    assert body["funnel"]["verified"] == 0
    assert body["funnel"]["paying"] == 0
    assert body["funnel"]["verification_rate"] == 0.0
    assert body["funnel"]["payer_conversion_rate"] == 0.0
    assert body["funnel"]["visited"] == 0
    assert body["funnel"]["cta_clicked"] == 0
    assert body["funnel"]["first_generation"] == 0
    assert body["funnel"]["exported"] == 0
    assert body["funnel"]["checkout_started"] == 0
    assert body["funnel"]["second_generation"] == 0
    assert body["funnel"]["analytics_enabled"] is False
    assert body["funnel"]["baseline_days"] == 0
    assert body["funnel"]["onboarding_gate_ready"] is False
    assert {"weekly", "source", "niche", "device"} == set(body["cohorts"])

    assert body["operations"]["queued_jobs"] == 1
    assert body["operations"]["processing_jobs"] == 1
    assert body["operations"]["completed_jobs"] == 2
    assert body["operations"]["failed_jobs"] == 1
    assert body["operations"]["success_rate"] == 50.0
    assert body["operations"]["avg_pending_credits"] == 1.5
    assert body["operations"]["orphan_dirs"] == 1
    assert body["operations"]["jobs_dir_size_gb"] > 0
    assert body["operations"]["output_dir_size_gb"] > 0

    package_mix = {item["package_name"]: item for item in body["package_mix"]}
    assert package_mix["starter"]["orders"] == 1
    assert package_mix["starter"]["approved_revenue_brl"] == 19.9
    assert package_mix["starter"]["net_revenue_brl"] == 19.9
    assert package_mix["starter"]["credits_sold"] == expected_credits_sold
    assert package_mix["popular"]["orders"] == 1
    assert package_mix["popular"]["approved_revenue_brl"] == 0.0

    revenue_points = {item["date"]: item["value"] for item in body["timeseries"]["revenue_by_day"]}
    jobs_points = {item["date"]: item["value"] for item in body["timeseries"]["jobs_by_day"]}
    users_points = {item["date"]: item["value"] for item in body["timeseries"]["new_users_by_day"]}
    recent_key = recent_created.date().isoformat()
    assert revenue_points[recent_key] == 19.9
    assert jobs_points[recent_key] == 4
    assert users_points[recent_key] == 2

    assert len(body["recent_activity"]["recent_users"]) >= 2
    assert body["recent_activity"]["recent_users"][0]["created_at"] is not None
    assert any(item["status"] == "pending" for item in body["recent_activity"]["recent_purchases"])
    assert body["recent_activity"]["recent_failed_jobs"][0]["error"] == "ffmpeg failed"


@pytest.mark.asyncio
async def test_admin_dashboard_rejects_invalid_range(client, admin_user, auth_headers):
    response = await client.get("/api/v1/admin/dashboard?range=365d", headers=auth_headers(admin_user))

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_admin_dashboard_uses_canonical_payment_precedence(
    client,
    db_session,
    verified_user,
    admin_user,
    auth_headers,
    purchase_factory,
):
    stale_approved = await purchase_factory(
        user_id=verified_user.id,
        status="approved",
        payment_state="refunded",
        package_name="starter",
    )
    rolling_paid = await purchase_factory(
        user_id=verified_user.id,
        status="pending",
        payment_state="paid",
        package_name="popular",
    )
    now = datetime.now(timezone.utc)
    await db_session.execute(
        update(CreditPurchase)
        .where(CreditPurchase.id.in_([stale_approved.id, rolling_paid.id]))
        .values(created_at=now, paid_at=now)
    )
    await db_session.execute(
        update(CreditPurchase).where(CreditPurchase.id == stale_approved.id).values(refunded_at=now)
    )
    await db_session.commit()

    response = await client.get("/api/v1/admin/dashboard?range=30d", headers=auth_headers(admin_user))

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["approved_orders"] == 2
    assert body["summary"]["paid_gross_revenue_brl"] == 69.8
    assert body["summary"]["refunded_value_brl"] == 19.9
    assert body["summary"]["net_revenue_brl"] == 49.9
    assert body["summary"]["approved_revenue_brl"] == 69.8
    assert body["summary"]["pending_orders"] == 0
    recent_states = {item["id"]: item["status"] for item in body["recent_activity"]["recent_purchases"]}
    assert recent_states[str(stale_approved.id)] == "refunded"
    assert recent_states[str(rolling_paid.id)] == "paid"


@pytest.mark.asyncio
async def test_admin_dashboard_links_anonymous_session_and_segments_cohort_without_pii(
    client,
    db_session,
    verified_user,
    admin_user,
    auth_headers,
    job_factory,
    monkeypatch,
):
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)
    monkeypatch.setattr(settings, "ANALYTICS_FRONTEND_ENABLED", True)
    now = datetime.now(timezone.utc)
    session_id = uuid.uuid4()
    job = await job_factory(user_id=verified_user.id, status="completed")
    await db_session.execute(
        update(User)
        .where(User.id == verified_user.id)
        .values(
            created_at=now - timedelta(days=2),
            utm_source="youtube",
            utm_medium="paid_social",
            utm_campaign="nicho-curiosidades",
        )
    )
    await db_session.execute(update(Job).where(Job.id == job.id).values(exported_at=now))
    started_at = now - timedelta(days=2)
    sequence = (
        "landing_viewed",
        "hero_cta_clicked",
        "user_registered",
        "email_verified",
        "generation_requested",
        "video_exported",
        "checkout_started",
        "payment_completed",
        "second_generation_requested",
    )
    db_session.add_all(
        [
            _analytics_event(
                event_name,
                started_at + timedelta(minutes=index),
                session_id=session_id if index < 2 else None,
                user_id=verified_user.id if index > 0 else None,
                authority="client" if index < 2 else "server",
                device_class="mobile" if index < 2 else "unknown",
            )
            for index, event_name in enumerate(sequence)
        ]
    )
    await db_session.commit()

    response = await client.get("/api/v1/admin/dashboard?range=30d", headers=auth_headers(admin_user))

    assert response.status_code == 200
    body = response.json()
    assert body["funnel"]["visited"] == 1
    assert body["funnel"]["cta_clicked"] == 1
    assert body["funnel"]["registered"] == 1
    assert body["funnel"]["verified"] == 1
    assert body["funnel"]["first_generation"] == 1
    assert body["funnel"]["exported"] == 1
    assert body["funnel"]["checkout_started"] == 1
    assert body["funnel"]["paying"] == 1
    assert body["funnel"]["second_generation"] == 1
    assert body["funnel"]["cta_registration_rate"] == 100.0
    assert body["funnel"]["export_payment_rate"] == 100.0
    assert body["funnel"]["analytics_enabled"] is True
    assert body["funnel"]["analytics_frontend_enabled"] is True
    assert body["funnel"]["collection_flags_aligned"] is True
    assert body["funnel"]["baseline_days"] == 0
    assert body["funnel"]["onboarding_gate_ready"] is False
    source_cohorts = {item["key"]: item for item in body["cohorts"]["source"]}
    niche_cohorts = {item["key"]: item for item in body["cohorts"]["niche"]}
    device_cohorts = {item["key"]: item for item in body["cohorts"]["device"]}
    assert source_cohorts["youtube"]["registered"] == 1
    assert niche_cohorts["curiosidades"]["registered"] == 1
    assert device_cohorts["mobile"]["registered"] == 1
    assert "email" not in source_cohorts["youtube"]


@pytest.mark.asyncio
async def test_onboarding_gate_requires_aligned_flags_and_fourteen_consecutive_collection_days(
    client,
    db_session,
    admin_user,
    auth_headers,
    monkeypatch,
):
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)
    monkeypatch.setattr(settings, "ANALYTICS_FRONTEND_ENABLED", True)
    now = datetime.now(timezone.utc)
    missing_day = 5
    db_session.add_all(
        [
            _analytics_event(
                "landing_viewed",
                now - timedelta(days=day),
                session_id=uuid.uuid4(),
                authority="client",
                device_class="mobile",
            )
            for day in range(14)
            if day != missing_day
        ]
    )
    await db_session.commit()

    with_gap = await client.get("/api/v1/admin/dashboard?range=30d", headers=auth_headers(admin_user))
    assert with_gap.status_code == 200
    assert with_gap.json()["funnel"]["baseline_days"] == missing_day
    assert with_gap.json()["funnel"]["onboarding_gate_ready"] is False

    db_session.add(
        _analytics_event(
            "landing_viewed",
            now - timedelta(days=missing_day),
            session_id=uuid.uuid4(),
            authority="client",
            device_class="mobile",
        )
    )
    await db_session.commit()
    complete = await client.get("/api/v1/admin/dashboard?range=7d", headers=auth_headers(admin_user))
    assert complete.status_code == 200
    assert complete.json()["funnel"]["baseline_days"] == 14
    assert complete.json()["funnel"]["onboarding_gate_ready"] is True

    monkeypatch.setattr(settings, "ANALYTICS_FRONTEND_ENABLED", False)
    misaligned = await client.get("/api/v1/admin/dashboard?range=30d", headers=auth_headers(admin_user))
    assert misaligned.status_code == 200
    assert misaligned.json()["funnel"]["collection_flags_aligned"] is False
    assert misaligned.json()["funnel"]["baseline_days"] == 0
    assert misaligned.json()["funnel"]["onboarding_gate_ready"] is False


@pytest.mark.asyncio
async def test_funnel_accepts_package_first_checkout_before_generation(
    client,
    db_session,
    verified_user,
    admin_user,
    auth_headers,
    monkeypatch,
):
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)
    monkeypatch.setattr(settings, "ANALYTICS_FRONTEND_ENABLED", True)
    now = datetime.now(timezone.utc) - timedelta(hours=1)
    session_id = uuid.uuid4()
    sequence = (
        ("landing_viewed", "client"),
        ("hero_cta_clicked", "client"),
        ("user_registered", "server"),
        ("email_verified", "server"),
        ("checkout_started", "server"),
        ("payment_completed", "server"),
        ("generation_requested", "server"),
        ("video_exported", "server"),
        ("second_generation_requested", "server"),
    )
    db_session.add_all(
        [
            _analytics_event(
                name,
                now + timedelta(minutes=index),
                session_id=session_id if authority == "client" else None,
                user_id=verified_user.id if index > 0 else None,
                authority=authority,
                device_class="mobile" if authority == "client" else "unknown",
            )
            for index, (name, authority) in enumerate(sequence)
        ]
    )
    await db_session.commit()

    response = await client.get("/api/v1/admin/dashboard?range=30d", headers=auth_headers(admin_user))

    assert response.status_code == 200
    funnel = response.json()["funnel"]
    assert funnel["verified"] == 1
    assert funnel["checkout_started"] == 1
    assert funnel["paying"] == 1
    assert funnel["first_generation"] == 1
    assert funnel["exported"] == 1
    assert funnel["second_generation"] == 1
    assert funnel["export_payment_rate"] == 0.0


@pytest.mark.asyncio
async def test_funnel_requires_temporal_order_for_each_linked_identity(
    client,
    db_session,
    verified_user,
    admin_user,
    auth_headers,
    monkeypatch,
):
    monkeypatch.setattr(settings, "ANALYTICS_ENABLED", True)
    monkeypatch.setattr(settings, "ANALYTICS_FRONTEND_ENABLED", True)
    now = datetime.now(timezone.utc)
    session_id = uuid.uuid4()
    events = [
        ("landing_viewed", 0, None, "client"),
        ("hero_cta_clicked", 1, verified_user.id, "client"),
        ("email_verified", 2, verified_user.id, "server"),
        ("user_registered", 3, verified_user.id, "server"),
        ("generation_requested", 4, verified_user.id, "server"),
        ("video_exported", 5, verified_user.id, "server"),
        ("checkout_started", 6, verified_user.id, "server"),
        ("payment_completed", 7, verified_user.id, "server"),
    ]
    db_session.add_all(
        [
            _analytics_event(
                name,
                now + timedelta(minutes=minute),
                session_id=session_id if authority == "client" else None,
                user_id=user_id,
                authority=authority,
                device_class="mobile" if authority == "client" else "unknown",
            )
            for name, minute, user_id, authority in events
        ]
    )
    await db_session.commit()

    response = await client.get("/api/v1/admin/dashboard?range=30d", headers=auth_headers(admin_user))

    assert response.status_code == 200
    funnel = response.json()["funnel"]
    assert funnel["visited"] == 1
    assert funnel["cta_clicked"] == 1
    assert funnel["registered"] == 1
    assert funnel["verified"] == 0
    assert funnel["first_generation"] == 0
    assert funnel["paying"] == 0
    assert all(
        0.0 <= funnel[key] <= 100.0
        for key in (
            "verification_rate",
            "payer_conversion_rate",
            "cta_registration_rate",
            "activation_rate",
            "export_payment_rate",
            "second_generation_rate",
        )
    )
