"""Feedback do beta: POST /feedback (widget e pos-video), listagem admin e welcome email."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.db.models import Feedback


@pytest.mark.asyncio
async def test_submit_widget_feedback(client, db_session, verified_user, auth_headers):
    response = await client.post(
        "/api/v1/feedback",
        json={"kind": "widget", "rating": 5, "comment": "Curti muito o editor!", "source_url": "/dashboard"},
        headers=auth_headers(verified_user),
    )

    assert response.status_code == 201
    rows = (await db_session.execute(select(Feedback).where(Feedback.user_id == verified_user.id))).scalars().all()
    assert len(rows) == 1
    assert rows[0].kind == "widget"
    assert rows[0].rating == 5
    assert rows[0].comment == "Curti muito o editor!"


@pytest.mark.asyncio
async def test_submit_post_video_feedback_with_job(client, db_session, verified_user, job_factory, auth_headers):
    job = await job_factory(status="completed")

    response = await client.post(
        "/api/v1/feedback",
        json={"kind": "post_video", "rating": 5, "job_id": str(job.id)},
        headers=auth_headers(verified_user),
    )

    assert response.status_code == 201
    row = (await db_session.execute(select(Feedback).where(Feedback.job_id == job.id))).scalar_one()
    assert row.kind == "post_video"


@pytest.mark.asyncio
async def test_feedback_rejects_job_of_another_user(
    client, other_verified_user, verified_user, job_factory, auth_headers
):
    foreign_job = await job_factory(user_id=other_verified_user.id)

    response = await client.post(
        "/api/v1/feedback",
        json={"kind": "post_video", "rating": 1, "job_id": str(foreign_job.id)},
        headers=auth_headers(verified_user),
    )

    assert response.status_code == 404, "Feedback so pode referenciar job do proprio usuario."


@pytest.mark.asyncio
async def test_feedback_validation(client, verified_user, auth_headers):
    headers = auth_headers(verified_user)

    out_of_range = await client.post("/api/v1/feedback", json={"kind": "widget", "rating": 6}, headers=headers)
    empty = await client.post("/api/v1/feedback", json={"kind": "widget"}, headers=headers)
    bad_kind = await client.post("/api/v1/feedback", json={"kind": "spam", "rating": 3}, headers=headers)

    assert out_of_range.status_code == 422, "Rating deve estar entre 1 e 5."
    assert empty.status_code == 422, "Feedback sem rating nem comentario nao diz nada."
    assert bad_kind.status_code == 422, "kind e um enum fechado."


@pytest.mark.asyncio
async def test_feedback_requires_auth(client):
    response = await client.post("/api/v1/feedback", json={"kind": "widget", "rating": 5})
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_admin_feedbacks_list_with_kind_filter(client, admin_user, verified_user, job_factory, auth_headers):
    job = await job_factory(status="completed")
    user_headers = auth_headers(verified_user)
    await client.post("/api/v1/feedback", json={"kind": "widget", "rating": 4, "comment": "bom"}, headers=user_headers)
    await client.post(
        "/api/v1/feedback", json={"kind": "post_video", "rating": 5, "job_id": str(job.id)}, headers=user_headers
    )

    all_response = await client.get("/api/v1/admin/feedbacks", headers=auth_headers(admin_user))
    widget_response = await client.get(
        "/api/v1/admin/feedbacks", params={"kind": "widget"}, headers=auth_headers(admin_user)
    )
    forbidden = await client.get("/api/v1/admin/feedbacks", headers=user_headers)

    assert all_response.status_code == 200
    assert all_response.json()["total"] == 2
    widget_data = widget_response.json()
    assert widget_data["total"] == 1
    assert widget_data["feedbacks"][0]["kind"] == "widget"
    assert widget_data["feedbacks"][0]["user_email"] == "verified@example.com"
    post_video = [f for f in all_response.json()["feedbacks"] if f["kind"] == "post_video"]
    assert post_video[0]["job_topic"] == "Topic", "Listagem traz o tema do job via join."
    assert forbidden.status_code == 403


@pytest.mark.asyncio
async def test_welcome_email_dispatched_on_verify(client, user_factory, monkeypatch):
    sent: list[tuple] = []
    monkeypatch.setattr("app.auth.routes.send_welcome_email", lambda *args: sent.append(args) or True)
    user = await user_factory(
        email="welcome@example.com",
        password_hash="hash",
        verification_code="123456",
        verification_expires=datetime.now(timezone.utc) + timedelta(minutes=10),
    )

    response = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": user.email, "code": "123456"},
    )

    assert response.status_code == 200
    assert len(sent) == 1, "Welcome email deve ser agendado na verificacao."
    assert sent[0][0] == "welcome@example.com"


@pytest.mark.asyncio
async def test_welcome_email_failure_does_not_break_verification(client, user_factory, monkeypatch):
    def _boom(*_args):
        raise RuntimeError("smtp down")

    monkeypatch.setattr("app.auth.routes.send_welcome_email", _boom)
    user = await user_factory(
        email="welcome-fail@example.com",
        password_hash="hash",
        verification_code="123456",
        verification_expires=datetime.now(timezone.utc) + timedelta(minutes=10),
    )

    response = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": user.email, "code": "123456"},
    )

    assert response.status_code == 200, "Falha no envio (background) nunca quebra a verificacao."
    assert response.json()["status"] == "verified"
