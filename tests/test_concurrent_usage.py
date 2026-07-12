import asyncio

import pytest

from app.db.models import CreditPurchase, Job, User


@pytest.mark.asyncio
async def test_concurrent_generate_with_one_credit_allows_only_one_success(
    client, db_session, verified_user, auth_headers
):
    db_user = await db_session.get(User, verified_user.id)
    db_user.credits = 1
    await db_session.commit()

    payload = {"topic": "Tema valido para concorrencia", "style": "educational", "duration_target": 45}
    responses = await asyncio.gather(
        client.post("/api/v1/generate", headers=auth_headers(verified_user), json=payload),
        client.post("/api/v1/generate", headers=auth_headers(verified_user), json=payload),
    )

    success_count = sum(response.status_code == 202 for response in responses)
    failure_count = sum(response.status_code == 402 for response in responses)
    fresh_user = await db_session.get(User, verified_user.id)
    await db_session.refresh(fresh_user)

    assert success_count == 1, "Only one concurrent generate call should succeed when one credit remains."
    assert failure_count == 1, "The competing generate call should fail with insufficient credits."
    assert fresh_user.credits == 0, "Concurrent generation should not overspend credits below zero."


@pytest.mark.asyncio
async def test_concurrent_verify_email_only_credits_once(client, db_session, unverified_user, monkeypatch):
    # Fixa o default publico (2): o .env local pode elevar WELCOME_CREDIT_BONUS no beta fechado.
    monkeypatch.setattr("app.auth.routes.settings.WELCOME_CREDIT_BONUS", 2)
    responses = await asyncio.gather(
        *[
            client.post(
                "/api/v1/auth/verify-email",
                json={"email": unverified_user.email, "code": unverified_user.verification_code},
            )
            for _ in range(5)
        ]
    )

    statuses = {response.json()["status"] for response in responses}
    refreshed_user = await db_session.get(User, unverified_user.id)

    assert "verified" in statuses, "One verification request should perform the OTP verification."
    assert "already_verified" in statuses, "Subsequent concurrent verification requests should become idempotent."
    assert refreshed_user.credits == 2, "Concurrent OTP verification should only grant credits once."


@pytest.mark.asyncio
async def test_concurrent_render_only_debits_pending_credits_once(
    client, db_session, job_factory, verified_user, auth_headers, storage_dir
):
    job = await job_factory(pending_credits=2.0)
    job_dir = storage_dir / "jobs" / str(job.id)
    job_dir.mkdir(parents=True)

    responses = await asyncio.gather(
        *[client.post(f"/api/v1/jobs/{job.id}/render", headers=auth_headers(verified_user)) for _ in range(2)]
    )

    success_count = sum(response.status_code == 200 for response in responses)
    refreshed_user = await db_session.get(User, verified_user.id)
    refreshed_job = await db_session.get(Job, job.id)

    assert success_count == 2, "Both render calls may return success once the first call clears pending credits."
    assert refreshed_user.credits == 3, "Concurrent render should charge the pending amount only once."
    assert refreshed_job.pending_credits == 0.0, "Concurrent render should leave no pending credits behind."


@pytest.mark.asyncio
async def test_webhook_replay_only_credits_purchase_once(
    client, db_session, purchase_factory, verified_user, monkeypatch
):
    purchase = await purchase_factory(package_name="starter")

    class _Sdk:
        class payment:
            @staticmethod
            def get(_payment_id):
                return {"response": {"status": "approved", "external_reference": str(purchase.id)}}

    monkeypatch.setattr("app.payments.service._get_sdk", lambda: _Sdk())

    payload = {"action": "payment.updated", "data": {"id": "999"}}
    responses = await asyncio.gather(*[client.post("/api/v1/webhooks/mercadopago", json=payload) for _ in range(5)])

    refreshed_purchase = await db_session.get(CreditPurchase, purchase.id)
    refreshed_user = await db_session.get(User, verified_user.id)

    assert all(
        response.status_code == 200 for response in responses
    ), "Webhook replay requests should be handled successfully."
    assert refreshed_purchase.status == "approved", "Approved webhook should finalize the purchase."
    assert refreshed_user.credits == 15, "Webhook replay must credit the user only once."
