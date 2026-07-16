from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_owner_downloads_archived_and_current_render_revisions(
    client,
    verified_user,
    auth_headers,
    job_factory,
    storage_dir,
):
    job = await job_factory(
        status="completed",
        editor_state={"composition": {"renderedRevision": 4}},
    )
    archive_dir = storage_dir / "output" / "revisions" / str(job.id)
    archive_dir.mkdir(parents=True)
    (archive_dir / "revision-3.mp4").write_bytes(b"revision-three")
    output_dir = storage_dir / "output"
    output_dir.mkdir(exist_ok=True)
    (output_dir / f"{job.id}.mp4").write_bytes(b"revision-four")

    archived = await client.get(
        f"/api/v1/jobs/{job.id}/revisions/3/download",
        headers=auth_headers(verified_user),
    )
    current = await client.get(
        f"/api/v1/jobs/{job.id}/revisions/4/download",
        headers=auth_headers(verified_user),
    )

    assert archived.status_code == 200
    assert archived.content == b"revision-three"
    assert "revision-3.mp4" in archived.headers["content-disposition"]
    assert current.status_code == 200
    assert current.content == b"revision-four"


@pytest.mark.asyncio
async def test_revision_download_is_private_and_rejects_negative_revision(
    client,
    verified_user,
    user_factory,
    auth_headers,
    job_factory,
    storage_dir,
):
    other = await user_factory(email="other-revision@example.com", verified=True)
    job = await job_factory(
        status="completed",
        editor_state={"composition": {"renderedRevision": 1}},
    )
    archive_dir = storage_dir / "output" / "revisions" / str(job.id)
    archive_dir.mkdir(parents=True)
    (archive_dir / "revision-0.mp4").write_bytes(b"private")

    forbidden = await client.get(
        f"/api/v1/jobs/{job.id}/revisions/0/download",
        headers=auth_headers(other),
    )
    invalid = await client.get(
        f"/api/v1/jobs/{job.id}/revisions/-1/download",
        headers=auth_headers(verified_user),
    )

    assert forbidden.status_code == 404
    assert invalid.status_code in {404, 422}
