import uuid

import pytest
from sqlalchemy import select

from app.db.models import CreditPurchase, User
from app.payments import routes as payments_routes


@pytest.mark.asyncio
async def test_register_verify_generate_status_and_download_flow(client, db_session, app, storage_dir):
    register = await client.post(
        "/api/v1/auth/register",
        json={"email": "flow@example.com", "name": "Flow User", "password": "Supersecret1"},
    )
    assert register.status_code == 201
    token = register.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    user = await db_session.scalar(select(User).where(User.email == "flow@example.com"))
    assert user is not None
    assert user.verification_code is not None

    verify = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": user.email, "code": user.verification_code},
    )
    assert verify.status_code == 200
    assert verify.json()["status"] == "verified"

    generate = await client.post(
        "/api/v1/generate",
        headers=headers,
        json={
            "topic": "Tema completo para fluxo ponta a ponta",
            "style": "educational",
            "duration_target": 45,
            "template_id": "stock_narration",
        },
    )
    assert generate.status_code == 202
    job_id = generate.json()["job_id"]

    app.state.fake_redis.hset(
        f"job:{job_id}",
        mapping={
            "status": "completed",
            "progress": "1",
            "current_step": "finalizing",
            "error": "",
            "detail": "Pronto",
            "created_at": "2026-04-04T12:00:00+00:00",
        },
    )
    output_path = storage_dir / "output" / f"{job_id}.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"video")

    status = await client.get(f"/api/v1/jobs/{job_id}", headers=headers)
    assert status.status_code == 200
    assert status.json()["status"] == "completed"

    status_poll = await client.get(f"/api/v1/jobs/{job_id}/status", headers=headers)
    assert status_poll.status_code == 200
    assert status_poll.json()["status"] == "completed"

    download = await client.get(f"/api/v1/jobs/{job_id}/download", headers=headers)
    assert download.status_code == 200
    assert download.headers["content-type"] == "video/mp4"


@pytest.mark.asyncio
async def test_credits_packages_checkout_and_history_flow(client, verified_user, auth_headers, monkeypatch):
    async def fake_create_checkout(user, package_key, db):
        purchase_id = uuid.uuid4()
        purchase = CreditPurchase(
            id=purchase_id,
            user_id=user.id,
            package_name=package_key,
            credits_amount=10,
            price_brl=1990,
            mp_preference_id="pref_123",
            status="pending",
        )
        db.add(purchase)
        await db.commit()
        return "https://payments.example/checkout", purchase_id

    monkeypatch.setattr(payments_routes, "create_checkout", fake_create_checkout)

    packages = await client.get("/api/v1/credits/packages", headers=auth_headers(verified_user))
    assert packages.status_code == 200
    assert len(packages.json()) >= 1

    checkout = await client.post(
        "/api/v1/credits/checkout",
        headers=auth_headers(verified_user),
        json={"package": "starter"},
    )
    assert checkout.status_code == 200
    assert checkout.json()["checkout_url"] == "https://payments.example/checkout"

    history = await client.get("/api/v1/credits/history", headers=auth_headers(verified_user))
    assert history.status_code == 200
    assert len(history.json()["purchases"]) == 1
