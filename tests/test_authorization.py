import uuid

import pytest


@pytest.mark.asyncio
async def test_job_status_requires_auth(client, job_factory):
    job = await job_factory()

    response = await client.get(f"/api/v1/jobs/{job.id}")

    assert response.status_code in {401, 403}


@pytest.mark.asyncio
async def test_job_status_wrong_user_returns_404(client, job_factory, other_verified_user, auth_headers):
    job = await job_factory()

    response = await client.get(f"/api/v1/jobs/{job.id}", headers=auth_headers(other_verified_user))

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_download_requires_auth(client, job_factory, storage_dir):
    job = await job_factory(status="completed")
    output_path = storage_dir / "output" / f"{job.id}.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"video")

    response = await client.get(f"/api/v1/jobs/{job.id}/download")

    assert response.status_code in {401, 403}


@pytest.mark.asyncio
async def test_download_wrong_user_returns_404(client, job_factory, other_verified_user, auth_headers, storage_dir):
    job = await job_factory(status="completed")
    output_path = storage_dir / "output" / f"{job.id}.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"video")

    response = await client.get(f"/api/v1/jobs/{job.id}/download", headers=auth_headers(other_verified_user))

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_composition_requires_auth(client, job_factory):
    job = await job_factory(script={"title": "x", "scenes": [], "narration": ""})

    response = await client.get(f"/api/v1/jobs/{job.id}/composition")

    assert response.status_code in {401, 403}


@pytest.mark.asyncio
async def test_composition_wrong_user_returns_404(client, job_factory, other_verified_user, auth_headers):
    job = await job_factory(script={"title": "x", "scenes": [], "narration": ""})

    response = await client.get(f"/api/v1/jobs/{job.id}/composition", headers=auth_headers(other_verified_user))

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_admin_stats_requires_admin(client, verified_user, auth_headers):
    response = await client.get("/api/v1/admin/storage-stats", headers=auth_headers(verified_user))

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_stats_works_for_admin(client, admin_user, auth_headers):
    response = await client.get("/api/v1/admin/storage-stats", headers=auth_headers(admin_user))

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_status_endpoint_wrong_user_returns_404(client, job_factory, other_verified_user, auth_headers, app):
    job = await job_factory()
    app.state.fake_redis.hset(f"job:{job.id}", mapping={"status": "processing", "progress": "0.4"})

    response = await client.get(f"/api/v1/jobs/{job.id}/status", headers=auth_headers(other_verified_user))

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_missing_owned_download_returns_404(client, verified_user, auth_headers):
    unknown_job_id = uuid.uuid4()

    response = await client.get(f"/api/v1/jobs/{unknown_job_id}/download", headers=auth_headers(verified_user))

    assert response.status_code == 404
