import pytest
from sqlalchemy import select

from app.db.models import User


@pytest.mark.asyncio
async def test_register_accepts_unicode_name_and_lowercases_email(client, db_session):
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "TeSt@Example.com", "name": "José 🚀", "password": "secret1"},
    )

    assert response.status_code == 201, "Registration should accept Unicode names."
    stored = await db_session.scalar(select(User).where(User.email == "test@example.com"))
    assert stored is not None, "Registration should persist the normalized email."


@pytest.mark.asyncio
async def test_register_rejects_blank_space_email_and_short_password(client):
    bad_email = await client.post(
        "/api/v1/auth/register",
        json={"email": " bad email ", "name": "User", "password": "secret1"},
    )
    short_password = await client.post(
        "/api/v1/auth/register",
        json={"email": "user@example.com", "name": "User", "password": "12345"},
    )

    assert bad_email.status_code == 422, "Invalid email formats should be rejected."
    assert short_password.status_code == 422, "Passwords shorter than six characters should be rejected."


@pytest.mark.asyncio
async def test_topic_length_boundaries_are_enforced(client, verified_user, auth_headers):
    at_limit = await client.post(
        "/api/v1/generate",
        headers=auth_headers(verified_user),
        json={"topic": "a" * 500, "style": "educational", "duration_target": 45},
    )
    over_limit = await client.post(
        "/api/v1/generate",
        headers=auth_headers(verified_user),
        json={"topic": "a" * 501, "style": "educational", "duration_target": 45},
    )

    assert at_limit.status_code == 200, "500-character topics should be accepted."
    assert over_limit.status_code == 422, "Topics longer than 500 characters should be rejected."


@pytest.mark.asyncio
async def test_job_of_another_user_returns_404_on_edit(client, user_factory, job_factory, auth_headers):
    other_user = await user_factory(
        email="other@example.com",
        password_hash="hash",
        credits=5,
        verified=True,
        verification_code=None,
        verification_expires=None,
    )
    job = await job_factory()

    response = await client.post(
        f"/api/v1/jobs/{job.id}/edit",
        headers=auth_headers(other_user),
        json={"editor_state": {"composition": {"scenes": []}}},
    )

    assert response.status_code == 404, "Editing another user's job should return 404 to avoid leaking job existence."
