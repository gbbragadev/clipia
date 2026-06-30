import json

import pytest


@pytest.mark.asyncio
async def test_generate_topic_too_short(client, verified_user, auth_headers):
    response = await client.post(
        "/api/v1/generate",
        headers=auth_headers(verified_user),
        json={"topic": "curto", "style": "educational", "duration_target": 45, "template_id": "stock_narration"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_generate_invalid_style(client, verified_user, auth_headers):
    response = await client.post(
        "/api/v1/generate",
        headers=auth_headers(verified_user),
        json={
            "topic": "Tema valido para gerar video",
            "style": "curiosity",
            "duration_target": 45,
            "template_id": "stock_narration",
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_generate_duration_out_of_range(client, verified_user, auth_headers):
    short_response = await client.post(
        "/api/v1/generate",
        headers=auth_headers(verified_user),
        json={
            "topic": "Tema valido para gerar video",
            "style": "educational",
            "duration_target": 10,
            "template_id": "stock_narration",
        },
    )
    long_response = await client.post(
        "/api/v1/generate",
        headers=auth_headers(verified_user),
        json={
            "topic": "Tema valido para gerar video",
            "style": "educational",
            "duration_target": 181,
            "template_id": "stock_narration",
        },
    )

    assert short_response.status_code == 422
    assert long_response.status_code == 422


@pytest.mark.asyncio
async def test_generate_invalid_template(client, verified_user, auth_headers):
    response = await client.post(
        "/api/v1/generate",
        headers=auth_headers(verified_user),
        json={
            "topic": "Tema valido para gerar video",
            "style": "educational",
            "duration_target": 45,
            "template_id": "missing",
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_edit_payload_too_large(client, verified_user, auth_headers, job_factory):
    job = await job_factory()
    editor_state = {"composition": {"scenes": [{"text": "a" * 600_000}]}}

    response = await client.post(
        f"/api/v1/jobs/{job.id}/edit",
        headers=auth_headers(verified_user) | {"Content-Type": "application/json"},
        content=json.dumps({"editor_state": editor_state}),
    )

    assert response.status_code == 413


@pytest.mark.asyncio
async def test_invalid_uuid_in_path(client, verified_user, auth_headers):
    response = await client.get("/api/v1/jobs/not-a-uuid/composition", headers=auth_headers(verified_user))

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_waitlist_invalid_email(client):
    response = await client.post("/api/v1/waitlist", json={"email": " bad email "})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_tts_invalid_voice(client, verified_user, auth_headers, job_factory, storage_dir):
    job = await job_factory(script={"title": "x", "scenes": [], "narration": "texto"})
    job_dir = storage_dir / "jobs" / str(job.id)
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "script.json").write_text(json.dumps({"narration": "texto"}), encoding="utf-8")

    response = await client.post(
        f"/api/v1/jobs/{job.id}/regenerate-tts",
        headers=auth_headers(verified_user),
        json={"voice_id": "pt-BR-VozInexistenteNeural"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_ai_suggest_message_too_long(client, verified_user, auth_headers, job_factory):
    job = await job_factory()

    response = await client.post(
        f"/api/v1/jobs/{job.id}/ai-suggest",
        headers=auth_headers(verified_user),
        json={"message": "a" * 1001, "context": {"title": "Video"}},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_ai_suggest_context_too_large(client, verified_user, auth_headers, job_factory):
    job = await job_factory()

    response = await client.post(
        f"/api/v1/jobs/{job.id}/ai-suggest",
        headers=auth_headers(verified_user),
        json={"message": "Melhore o roteiro", "context": {"blob": "a" * 110_000}},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_global_500_handler_hides_internal_details(client, verified_user, auth_headers, job_factory, storage_dir):
    job = await job_factory()
    job_dir = storage_dir / "jobs" / str(job.id)
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "script.json").write_text("{bad json", encoding="utf-8")

    response = await client.get(f"/api/v1/jobs/{job.id}/composition", headers=auth_headers(verified_user))

    assert response.status_code == 500
    assert response.json()["detail"] == "Erro interno. Tente novamente."
