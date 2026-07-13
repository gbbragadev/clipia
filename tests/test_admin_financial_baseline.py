import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import update

from app import observability
from app.db.models import CreditPurchase, Job, JobDispatch, User


async def _set_times(db_session, model, row_id, **values) -> None:
    await db_session.execute(update(model).where(model.id == row_id).values(**values))


@pytest.mark.asyncio
async def test_dashboard_uses_paid_at_and_limits_payers_to_registered_cohort(
    client,
    db_session,
    verified_user,
    other_verified_user,
    admin_user,
    auth_headers,
    purchase_factory,
):
    now = datetime.now(timezone.utc)
    recent = now - timedelta(days=2)
    old = now - timedelta(days=45)

    inside_paid = await purchase_factory(
        user_id=verified_user.id,
        package_name="starter",
        status="pending",
        payment_state="paid",
    )
    outside_paid = await purchase_factory(
        user_id=other_verified_user.id,
        package_name="popular",
        status="pending",
        payment_state="paid",
    )
    created_inside_but_paid_old = await purchase_factory(
        user_id=verified_user.id,
        package_name="pro",
        status="pending",
        payment_state="paid",
    )

    await _set_times(db_session, User, verified_user.id, created_at=recent)
    await _set_times(db_session, User, other_verified_user.id, created_at=old)
    await _set_times(db_session, User, admin_user.id, created_at=old)
    await _set_times(db_session, CreditPurchase, inside_paid.id, created_at=old, paid_at=recent)
    await _set_times(db_session, CreditPurchase, outside_paid.id, created_at=old, paid_at=recent)
    await _set_times(
        db_session,
        CreditPurchase,
        created_inside_but_paid_old.id,
        created_at=recent,
        paid_at=old,
    )
    await db_session.commit()

    response = await client.get("/api/v1/admin/dashboard?range=30d", headers=auth_headers(admin_user))

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["paid_gross_revenue_brl"] == 69.8
    assert body["summary"]["net_revenue_brl"] == 69.8
    assert body["summary"]["approved_revenue_brl"] == 69.8
    assert body["summary"]["approved_orders"] == 2
    assert body["funnel"]["registered"] == 0
    assert body["funnel"]["paying"] == 0
    assert body["funnel"]["payer_conversion_rate"] == 0.0

    revenue_points = {item["date"]: item["value"] for item in body["timeseries"]["revenue_by_day"]}
    assert revenue_points[recent.date().isoformat()] == 69.8


@pytest.mark.asyncio
async def test_dashboard_separates_pending_paid_refunded_and_uses_frozen_bonus(
    client,
    db_session,
    admin_user,
    auth_headers,
    purchase_factory,
):
    recent = datetime.now(timezone.utc) - timedelta(days=1)
    paid = await purchase_factory(
        package_name="starter",
        status="pending",
        payment_state="paid",
        bonus_credits=2,
    )
    pending = await purchase_factory(
        package_name="popular",
        status="pending",
        payment_state="pending",
        bonus_credits=6,
    )
    refunded = await purchase_factory(
        package_name="pro",
        status="approved",
        payment_state="refunded",
        bonus_credits=20,
    )
    for purchase in (paid, pending, refunded):
        values = {"created_at": recent}
        if purchase is paid:
            values["paid_at"] = recent
        elif purchase is refunded:
            values["refunded_at"] = recent
        await _set_times(db_session, CreditPurchase, purchase.id, **values)
    await db_session.commit()

    response = await client.get("/api/v1/admin/dashboard?range=30d", headers=auth_headers(admin_user))

    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["paid_gross_revenue_brl"] == 19.9
    assert summary["pending_checkout_value_brl"] == 49.9
    assert summary["refunded_value_brl"] == 129.9
    assert summary["net_revenue_brl"] == -110.0
    assert summary["approved_orders"] == 1
    assert summary["pending_orders"] == 1
    assert summary["refunded_orders"] == 1
    assert summary["credits_sold"] == 12
    assert summary["invalid_purchase_rows"] == 0


@pytest.mark.asyncio
async def test_dashboard_uses_refunded_at_for_old_and_refund_before_paid_purchases(
    client,
    db_session,
    admin_user,
    auth_headers,
    purchase_factory,
):
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=90)
    recent = now - timedelta(days=1)
    old_paid_then_refunded = await purchase_factory(
        package_name="starter",
        status="refunded",
        payment_state="refunded",
    )
    refund_before_paid = await purchase_factory(
        package_name="popular",
        status="refunded",
        payment_state="refunded",
    )
    await _set_times(
        db_session,
        CreditPurchase,
        old_paid_then_refunded.id,
        created_at=old,
        paid_at=old,
        refunded_at=recent,
    )
    await _set_times(
        db_session,
        CreditPurchase,
        refund_before_paid.id,
        created_at=old,
        paid_at=None,
        refunded_at=recent,
    )
    await db_session.commit()

    response = await client.get("/api/v1/admin/dashboard?range=30d", headers=auth_headers(admin_user))

    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["refunded_orders"] == 2
    assert summary["refunded_value_brl"] == 69.8
    assert summary["paid_gross_revenue_brl"] == 0.0
    assert summary["net_revenue_brl"] == -69.8
    assert summary["invalid_purchase_rows"] == 0


@pytest.mark.asyncio
async def test_dashboard_operation_baseline_uses_completed_dispatch_snapshots(
    client,
    db_session,
    verified_user,
    admin_user,
    auth_headers,
    job_factory,
):
    generation_job = await job_factory(user_id=verified_user.id, status="editable")
    rerender_job = await job_factory(user_id=verified_user.id, status="completed")
    cancelled_job = await job_factory(user_id=verified_user.id, status="failed")
    pending_job = await job_factory(user_id=verified_user.id, status="processing")

    rows = [
        JobDispatch(
            job_id=generation_job.id,
            operation_id=generation_job.id,
            kind="generation",
            payload={},
            debited_credits=3,
            state="completed",
        ),
        JobDispatch(
            job_id=rerender_job.id,
            operation_id=uuid.uuid4(),
            kind="rerender",
            payload={},
            debited_credits=2,
            state="completed",
        ),
        JobDispatch(
            job_id=cancelled_job.id,
            operation_id=cancelled_job.id,
            kind="generation",
            payload={},
            debited_credits=9,
            state="cancelled",
        ),
        JobDispatch(
            job_id=pending_job.id,
            operation_id=uuid.uuid4(),
            kind="rerender",
            payload={},
            debited_credits=5,
            state="pending",
        ),
    ]
    db_session.add_all(rows)
    await db_session.commit()

    response = await client.get("/api/v1/admin/dashboard?range=30d", headers=auth_headers(admin_user))

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["credits_consumed"] == 5
    assert body["operations"]["delivered_generation_operations"] == 1
    assert body["operations"]["delivered_rerender_operations"] == 1
    assert body["operations"]["cancelled_generation_operations"] == 1
    assert body["operations"]["active_rerender_operations"] == 1
    assert body["operations"]["delivered_operations"] == 2
    assert body["operations"]["operation_success_rate"] == 66.67


@pytest.mark.asyncio
async def test_observability_authoritative_credit_totals_ignore_process_local_counters(
    test_db,
    db_session,
    verified_user,
    purchase_factory,
    job_factory,
):
    paid = await purchase_factory(
        user_id=verified_user.id,
        package_name="starter",
        status="pending",
        payment_state="paid",
        bonus_credits=2,
    )
    await purchase_factory(
        user_id=verified_user.id,
        package_name="popular",
        status="pending",
        payment_state="pending",
        bonus_credits=6,
    )
    delivered_job = await job_factory(user_id=verified_user.id, status="editable")
    await _set_times(db_session, CreditPurchase, paid.id, paid_at=datetime.now(timezone.utc))
    db_session.add(
        JobDispatch(
            job_id=delivered_job.id,
            operation_id=delivered_job.id,
            kind="generation",
            payload={},
            debited_credits=3,
            state="completed",
        )
    )
    await db_session.commit()

    @asynccontextmanager
    async def runtime_session():
        async with test_db["session_factory"]() as session:
            yield session

    original = observability._runtime_session
    observability._runtime_session = runtime_session
    try:
        with observability._METRIC_LOCK:
            observability._CREDIT_TOTALS.clear()
        observability.record_credit_metric("credit", 500)
        observability.record_credit_metric("debit", 400)

        totals = await observability._get_credit_totals()
    finally:
        observability._runtime_session = original
        with observability._METRIC_LOCK:
            observability._CREDIT_TOTALS.clear()

    assert totals == {"purchased": 12.0, "consumed": 3.0}


@pytest.mark.asyncio
async def test_admin_economy_labels_partial_telemetry_as_estimate(
    client,
    db_session,
    admin_user,
    auth_headers,
    job_factory,
):
    job = await job_factory(status="editable")
    await _set_times(
        db_session,
        Job,
        job.id,
        telemetry={"api_cost_usd_est": 0.42, "total_seconds": 12.5, "steps": {}},
    )
    await db_session.commit()

    response = await client.get("/api/v1/admin/economy", headers=auth_headers(admin_user))

    assert response.status_code == 200
    body = response.json()
    assert body["basis"] == "estimate"
    assert body["telemetry_jobs"] == 1
    assert "nao representa COGS real" in body["limitations"]
    assert body["jobs"][0]["api_cost_usd_est"] == 0.42
