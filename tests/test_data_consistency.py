import json

import pytest
from sqlalchemy import delete

from app.db.models import CreditPurchase, Job, User


@pytest.mark.asyncio
async def test_edit_persists_editor_state_and_composition_reads_it(client, db_session, job_factory, verified_user, auth_headers, storage_dir):
    job = await job_factory(script={"scenes": [{"text": "scene 1"}]}, editor_state=None)
    job_dir = storage_dir / "jobs" / str(job.id)
    (job_dir / "media").mkdir(parents=True)
    (job_dir / "script.json").write_text(json.dumps({"scenes": [{"text": "scene 1"}]}), encoding="utf-8")
    (job_dir / "words.json").write_text(json.dumps([{"word": "oi", "start": 0.0, "end": 0.5}]), encoding="utf-8")
    (job_dir / "narration.wav").write_bytes(b"audio")

    editor_state = {"composition": {"scenes": [{"text": "editada"}], "words": [{"word": "oi"}]}}
    save = await client.post(
        f"/api/v1/jobs/{job.id}/edit",
        headers=auth_headers(verified_user),
        json={"editor_state": editor_state},
    )
    composition = await client.get(f"/api/v1/jobs/{job.id}/composition", headers=auth_headers(verified_user))

    assert save.status_code == 200, "Editor state should save successfully."
    assert composition.status_code == 200, "Saved composition should be retrievable."
    assert composition.json()["editor_state"] == editor_state, "Composition should return the saved editor_state."


@pytest.mark.asyncio
async def test_jobs_endpoint_falls_back_to_database_status_when_redis_is_empty(client, job_factory, verified_user, auth_headers):
    job = await job_factory(status="completed")
    response = await client.get("/api/v1/jobs", headers=auth_headers(verified_user))

    assert response.status_code == 200, "Jobs list should succeed for authenticated users."
    listed = next(item for item in response.json() if item["job_id"] == str(job.id))
    assert listed["status"] == "completed", "Jobs list should fall back to persisted DB status when Redis has no entry."


@pytest.mark.asyncio
async def test_foreign_key_constraints_block_orphan_jobs_and_purchases(db_session, verified_user):
    orphan_job = Job(user_id=verified_user.id, topic="x", style="educational", duration_target=45)
    orphan_purchase = CreditPurchase(
        user_id=verified_user.id,
        package_name="starter",
        credits_amount=10,
        price_brl=1990,
        mp_preference_id="pref_1",
        status="pending",
    )
    db_session.add_all([orphan_job, orphan_purchase])
    await db_session.commit()

    with pytest.raises(Exception):
        await db_session.execute(delete(User).where(User.id == verified_user.id))
        await db_session.commit()
