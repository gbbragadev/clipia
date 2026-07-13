import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import update

from app.db.models import CreditPurchase, Job, JobDispatch, User


def _write_file(path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


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

    assert body["funnel"]["registered"] == 2
    assert body["funnel"]["verified"] == 1
    assert body["funnel"]["paying"] == 1
    assert body["funnel"]["verification_rate"] == 50.0
    assert body["funnel"]["payer_conversion_rate"] == 50.0

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
    await db_session.execute(
        update(CreditPurchase)
        .where(CreditPurchase.id.in_([stale_approved.id, rolling_paid.id]))
        .values(created_at=datetime.now(timezone.utc), paid_at=datetime.now(timezone.utc))
    )
    await db_session.commit()

    response = await client.get("/api/v1/admin/dashboard?range=30d", headers=auth_headers(admin_user))

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["approved_orders"] == 1
    assert body["summary"]["approved_revenue_brl"] == 49.9
    assert body["summary"]["pending_orders"] == 0
    recent_states = {item["id"]: item["status"] for item in body["recent_activity"]["recent_purchases"]}
    assert recent_states[str(stale_approved.id)] == "refunded"
    assert recent_states[str(rolling_paid.id)] == "paid"
