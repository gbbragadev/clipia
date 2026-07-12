import asyncio

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

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
async def test_concurrent_verify_email_only_credits_once_without_process_lock(
    client, db_session, unverified_user, monkeypatch
):
    # Fixa o default publico (2): o .env local pode elevar WELCOME_CREDIT_BONUS no beta fechado.
    monkeypatch.setattr("app.auth.routes.settings.WELCOME_CREDIT_BONUS", 2)
    db_user = await db_session.get(User, unverified_user.id)
    db_user.credits = 7
    await db_session.commit()

    class _IndependentLock:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

    monkeypatch.setattr("app.auth.routes.get_lock", lambda _key: _IndependentLock())

    request_count = 5
    reads_ready = asyncio.Event()
    initial_reads = 0
    original_execute = AsyncSession.execute

    async def execute_after_shared_snapshot(self, statement, *args, **kwargs):
        nonlocal initial_reads
        result = await original_execute(self, statement, *args, **kwargs)
        if getattr(statement, "is_select", False) and initial_reads < request_count:
            initial_reads += 1
            await self.commit()
            if initial_reads == request_count:
                reads_ready.set()
            await reads_ready.wait()
        return result

    monkeypatch.setattr(AsyncSession, "execute", execute_after_shared_snapshot)

    credit_metrics = []
    monkeypatch.setattr(
        "app.auth.routes.record_credit_metric",
        lambda metric_type, amount: credit_metrics.append((metric_type, amount)),
    )

    responses = await asyncio.gather(
        *[
            client.post(
                "/api/v1/auth/verify-email",
                json={"email": unverified_user.email, "code": unverified_user.verification_code},
            )
            for _ in range(request_count)
        ]
    )

    assert all(response.status_code == 200 for response in responses)
    statuses = [response.json()["status"] for response in responses]
    db_session.expire_all()
    refreshed_user = await db_session.get(User, unverified_user.id)

    assert statuses.count("verified") == 1, "Only one request should perform the protected verification transition."
    assert statuses.count("already_verified") == request_count - 1
    assert refreshed_user.credits == 9, "Concurrent OTP verification should add the bonus exactly once."
    assert credit_metrics.count(("credit", 2)) == 1


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
