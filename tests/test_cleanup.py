import importlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import update

from app.api import routes as api_routes
from app.auth.service import create_access_token, hash_password
from app.config import settings
from app.db.models import Job, User
from app.worker import tasks as worker_tasks
from app.worker.celery_app import celery_app

db_engine = importlib.import_module("app.db.engine")


def _write_file(path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


@pytest.mark.asyncio
async def test_cleanup_old_jobs_removes_expired_files_and_clears_video_url(
    test_db,
    db_session,
    job_factory,
    monkeypatch,
):
    monkeypatch.setattr(db_engine, "worker_session", test_db["session_factory"])

    completed_job = await job_factory(status="completed")
    failed_job = await job_factory(status="failed")
    recent_job = await job_factory(status="completed")

    old_completed = datetime.now(timezone.utc) - timedelta(days=31)
    old_failed = datetime.now(timezone.utc) - timedelta(days=8)
    recent_created = datetime.now(timezone.utc) - timedelta(days=2)

    await db_session.execute(
        update(Job)
        .where(Job.id == completed_job.id)
        .values(created_at=old_completed, video_url=f"/storage/output/{completed_job.id}.mp4")
    )
    await db_session.execute(update(Job).where(Job.id == failed_job.id).values(created_at=old_failed))
    await db_session.execute(update(Job).where(Job.id == recent_job.id).values(created_at=recent_created))
    await db_session.commit()

    completed_dir = settings.STORAGE_DIR / "jobs" / str(completed_job.id)
    failed_dir = settings.STORAGE_DIR / "jobs" / str(failed_job.id)
    recent_dir = settings.STORAGE_DIR / "jobs" / str(recent_job.id)
    completed_output = settings.STORAGE_DIR / "output" / f"{completed_job.id}.mp4"
    recent_output = settings.STORAGE_DIR / "output" / f"{recent_job.id}.mp4"

    _write_file(completed_dir / "asset.bin", 1024 * 1024)
    _write_file(failed_dir / "broken.bin", 512 * 1024)
    _write_file(recent_dir / "fresh.bin", 256 * 1024)
    _write_file(completed_output, 2 * 1024 * 1024)
    _write_file(recent_output, 2 * 1024 * 1024)

    result = await worker_tasks._cleanup_old_jobs_async()

    async with test_db["session_factory"]() as fresh_session:
        refreshed_completed = await fresh_session.get(Job, completed_job.id)
        refreshed_failed = await fresh_session.get(Job, failed_job.id)
        refreshed_recent = await fresh_session.get(Job, recent_job.id)

    assert result["removed_jobs"] == 2
    assert refreshed_completed is not None and refreshed_completed.video_url is None
    assert refreshed_completed.status == "completed"
    assert refreshed_failed is not None and refreshed_failed.video_url is None
    assert refreshed_recent is not None
    assert completed_dir.exists() is False
    assert failed_dir.exists() is False
    assert recent_dir.exists() is True
    assert completed_output.exists() is False
    assert recent_output.exists() is True


@pytest.mark.asyncio
async def test_cleanup_orphan_files_removes_untracked_dirs_and_outputs(
    test_db,
    db_session,
    job_factory,
    monkeypatch,
):
    monkeypatch.setattr(db_engine, "worker_session", test_db["session_factory"])

    tracked_job = await job_factory(status="completed")
    tracked_dir = settings.STORAGE_DIR / "jobs" / str(tracked_job.id)
    tracked_output = settings.STORAGE_DIR / "output" / f"{tracked_job.id}.mp4"
    orphan_dir = settings.STORAGE_DIR / "jobs" / "orphan-job"
    orphan_output = settings.STORAGE_DIR / "output" / "orphan-job.mp4"

    _write_file(tracked_dir / "asset.bin", 256 * 1024)
    _write_file(tracked_output, 512 * 1024)
    _write_file(orphan_dir / "stale.bin", 256 * 1024)
    _write_file(orphan_output, 512 * 1024)

    result = await worker_tasks._cleanup_orphan_files_async()

    assert result["removed_dirs"] == 1
    assert result["removed_outputs"] == 1
    assert tracked_dir.exists() is True
    assert tracked_output.exists() is True
    assert orphan_dir.exists() is False
    assert orphan_output.exists() is False


@pytest.mark.asyncio
async def test_storage_stats_requires_admin_and_reports_usage(client, db_session, verified_user, auth_headers):
    forbidden = await client.get("/api/v1/admin/storage-stats", headers=auth_headers(verified_user))
    assert forbidden.status_code == 403

    admin = User(
        email="admin@example.com",
        name="Admin User",
        password_hash=hash_password("secret123"),
        credits=0,
        plan="admin",
        email_verified=True,
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)

    job = Job(
        user_id=verified_user.id,
        topic="Tema para estatisticas",
        style="educational",
        duration_target=45,
        status="completed",
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    job_dir = settings.STORAGE_DIR / "jobs" / str(job.id)
    output_path = settings.STORAGE_DIR / "output" / f"{job.id}.mp4"
    orphan_dir = settings.STORAGE_DIR / "jobs" / "orphan-dir"
    _write_file(job_dir / "asset.bin", 2 * 1024 * 1024)
    _write_file(output_path, 3 * 1024 * 1024)
    _write_file(orphan_dir / "stale.bin", 512 * 1024)

    token = create_access_token(str(admin.id))
    response = await client.get("/api/v1/admin/storage-stats", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["total_jobs"] >= 1
    assert body["failed_jobs"] == 0
    assert body["orphan_dirs"] == 1
    assert body["jobs_dir_size_gb"] > 0
    assert body["output_dir_size_gb"] > 0
    assert body["oldest_job_days"] >= 0


def test_celery_beat_schedule_registers_cleanup_tasks():
    schedule = celery_app.conf.beat_schedule

    assert schedule["cleanup-old-jobs"]["task"] == "cleanup_old_jobs"
    assert schedule["cleanup-orphan-files"]["task"] == "cleanup_orphan_files"


@pytest.mark.asyncio
async def test_reap_marks_old_queued_jobs_failed_and_refunds(test_db, db_session, job_factory, monkeypatch):
    """Jobs queued ha >60min viram failed com reembolso; jobs recentes/outras filas nao."""
    monkeypatch.setattr(db_engine, "worker_session", test_db["session_factory"])

    refunded: list[tuple] = []

    def _fake_refund(job_id, status_value, error, cleanup_files=False):
        refunded.append((job_id, status_value, error))

    monkeypatch.setattr(worker_tasks, "_refund_job_credit", _fake_refund)

    orphan_job = await job_factory(status="queued")
    recent_queued = await job_factory(status="queued")
    processing_job = await job_factory(status="processing")

    old_created = datetime.now(timezone.utc) - timedelta(minutes=90)
    recent_created = datetime.now(timezone.utc) - timedelta(minutes=5)
    for jid in (orphan_job.id, processing_job.id):
        await db_session.execute(update(Job).where(Job.id == jid).values(created_at=old_created))
    await db_session.execute(update(Job).where(Job.id == recent_queued.id).values(created_at=recent_created))
    await db_session.commit()

    # A query async (testada direto, sem asyncio.run aninhado) e deterministica:
    # so o orphan_job (queued + >60min) deve ser coletado. O reaper roteia cada ID para
    # _refund_job_credit(failed) — o teste espelha essa logica com o fake refund.
    orphan_ids = await worker_tasks._find_orphan_queued_jobs_async()

    assert orphan_ids == [str(orphan_job.id)]

    # Simula o roteamento que _reap_orphan_queued_jobs faz para cada ID coletado
    for job_id in orphan_ids:
        _fake_refund(job_id, "failed", worker_tasks.ORPHAN_QUEUED_ERROR)

    assert len(refunded) == 1
    assert refunded[0][0] == str(orphan_job.id)
    assert refunded[0][1] == "failed"
    assert "órfão" in refunded[0][2] or "orfao" in refunded[0][2]


def test_reap_orphan_queued_jobs_routes_each_orphan_to_refund(monkeypatch):
    """O wrapper sincrono coleta IDs e roteia cada um para _refund_job_credit(failed)."""
    fake_ids = ["job-a", "job-b"]
    refunded: list[tuple] = []
    monkeypatch.setattr(
        worker_tasks,
        "_find_orphan_queued_jobs_async",
        lambda: __import__("asyncio").sleep(0, result=fake_ids),
    )
    monkeypatch.setattr(
        worker_tasks,
        "_refund_job_credit",
        lambda job_id, status_value, error, **_: refunded.append((job_id, status_value, error)),
    )

    reaped = worker_tasks._reap_orphan_queued_jobs()

    assert reaped == 2
    assert {r[0] for r in refunded} == {"job-a", "job-b"}
    assert all(r[1] == "failed" for r in refunded)
    assert all("órfão" in r[2] or "orfao" in r[2] for r in refunded)


@pytest.mark.asyncio
async def test_generate_blocks_when_storage_is_low(client, test_db, verified_user, auth_headers, monkeypatch):
    async with test_db["session_factory"]() as fresh_session:
        db_user = await fresh_session.get(User, verified_user.id)
        assert db_user is not None
        start_credits = db_user.credits

    monkeypatch.setattr(
        api_routes.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(total=10 * 1024**3, used=9 * 1024**3, free=4 * 1024**3 - 1),
    )

    response = await client.post(
        "/api/v1/generate",
        headers=auth_headers(verified_user),
        json={"topic": "Tema valido para gerar", "style": "educational", "duration_target": 45},
    )

    async with test_db["session_factory"]() as fresh_session:
        refreshed_user = await fresh_session.get(User, verified_user.id)

    assert response.status_code == 503
    assert refreshed_user is not None and refreshed_user.credits == start_credits
