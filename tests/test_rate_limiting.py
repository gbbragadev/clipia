import pytest

from app.db.models import User


@pytest.mark.asyncio
async def test_auth_register_limit_blocks_sixth_request(client_factory):
    async with client_factory("10.0.0.1") as client:
        responses = []
        for idx in range(6):
            responses.append(await client.post(
                "/api/v1/auth/register",
                json={"email": f"user{idx}@example.com", "name": f"User {idx}", "password": "Secret123"},
            ))

    assert responses[4].status_code == 201, "The fifth register request should still be accepted."
    assert responses[5].status_code == 429, "The sixth register request from one IP should be rate limited."


@pytest.mark.asyncio
async def test_generate_limit_is_per_ip_and_does_not_block_other_ips(client_factory, db_session, verified_user, auth_headers):
    db_user = await db_session.get(User, verified_user.id)
    db_user.credits = 20
    await db_session.commit()

    payload = {"topic": "Tema valido para limite", "style": "educational", "duration_target": 45}

    async with client_factory("10.0.0.2") as client_a:
        responses_a = [
            await client_a.post("/api/v1/generate", headers=auth_headers(verified_user), json=payload)
            for _ in range(11)
        ]

    async with client_factory("10.0.0.3") as client_b:
        response_b = await client_b.post("/api/v1/generate", headers=auth_headers(verified_user), json=payload)

    assert responses_a[9].status_code == 200, "The tenth generate request should still be accepted."
    assert responses_a[10].status_code == 429, "The eleventh generate request from one IP should be rate limited."
    assert response_b.status_code == 200, "A different IP should not be blocked by another IP's rate limit."


@pytest.mark.asyncio
async def test_resend_code_limit_returns_429(client, unverified_user):
    responses = [
        await client.post("/api/v1/auth/resend-code", json={"email": unverified_user.email})
        for _ in range(4)
    ]

    assert responses[2].status_code == 200, "The third resend-code request should still be accepted."
    assert responses[3].status_code == 429, "The fourth resend-code request should hit the 3/minute limit."
