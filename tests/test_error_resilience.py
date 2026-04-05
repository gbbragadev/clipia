import json

import pytest


@pytest.mark.asyncio
async def test_invalid_json_and_missing_fields_return_422(client):
    invalid_json = await client.post(
        "/api/v1/auth/register",
        content=b"{invalid",
        headers={"Content-Type": "application/json"},
    )
    missing_fields = await client.post("/api/v1/generate", json={})

    assert invalid_json.status_code == 422, "Malformed JSON bodies should return 422 through FastAPI validation."
    assert missing_fields.status_code in {401, 403, 422}, "Missing request fields should not produce a successful response."


@pytest.mark.asyncio
async def test_invalid_uuid_and_missing_files_are_handled_gracefully(client, verified_user, auth_headers):
    invalid_uuid = await client.get("/api/v1/jobs/not-a-uuid/composition", headers=auth_headers(verified_user))
    missing_video = await client.get(f"/api/v1/jobs/{'0' * 8}-{ '0' * 4}-{ '0' * 4}-{ '0' * 4}-{ '0' * 12}/download", headers=auth_headers(verified_user))

    assert invalid_uuid.status_code == 422, "Invalid job ids should be rejected before touching storage."
    assert missing_video.status_code == 404, "Missing downloads should return 404."


@pytest.mark.asyncio
async def test_corrupted_composition_json_returns_server_error(client, job_factory, verified_user, auth_headers, storage_dir):
    job = await job_factory()
    job_dir = storage_dir / "jobs" / str(job.id)
    job_dir.mkdir(parents=True)
    (job_dir / "script.json").write_text("{bad json", encoding="utf-8")

    response = await client.get(f"/api/v1/jobs/{job.id}/composition", headers=auth_headers(verified_user))
    assert response.status_code == 500, "Corrupted composition files currently surface as a server error instead of crashing the process."


@pytest.mark.asyncio
async def test_webhook_invalid_json_payload_is_reported(client):
    response = await client.post(
        "/api/v1/webhooks/mercadopago",
        content=b"{bad json",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200, "Webhook invalid payloads should still get a handled response."
    assert response.json()["status"] == "invalid_payload", "Webhook invalid JSON should return invalid_payload."
