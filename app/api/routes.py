from datetime import datetime, timezone
from pathlib import Path

import redis
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.config import settings
from app.db.engine import get_db
from app.db.models import Job, User, WaitlistEntry
from app.models import GenerateRequest, JobStatus
from app.worker.tasks import dispatch_pipeline

router = APIRouter()
_redis = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


@router.post("/generate")
async def generate(
    req: GenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.credits < 1:
        raise HTTPException(status_code=402, detail="Créditos insuficientes")

    job = Job(
        user_id=user.id,
        topic=req.topic,
        style=req.style,
        duration_target=req.duration_target,
        status="queued",
    )
    db.add(job)
    user.credits -= 1
    await db.commit()
    await db.refresh(job)

    job_id = str(job.id)

    _redis.hset(f"job:{job_id}", mapping={
        "status": "queued",
        "progress": "0",
        "current_step": "",
        "error": "",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    dispatch_pipeline(job_id, req.topic, req.style, req.duration_target)

    return {"job_id": job_id, "status": "queued"}


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    data = _redis.hgetall(f"job:{job_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatus(
        job_id=job_id,
        status=data.get("status", "unknown"),
        progress=float(data.get("progress", 0)),
        current_step=data.get("current_step") or None,
        error=data.get("error") or None,
        created_at=data.get("created_at", ""),
        download_url=f"/api/v1/jobs/{job_id}/download" if data.get("status") == "completed" else None,
    )


@router.get("/jobs/{job_id}/download")
def download_job(job_id: str):
    file_path = Path(settings.STORAGE_DIR) / "output" / f"{job_id}.mp4"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Video not found")
    return FileResponse(str(file_path), media_type="video/mp4", filename=f"clipia-{job_id[:8]}.mp4")


class WaitlistRequest(BaseModel):
    email: str


@router.post("/waitlist", status_code=201)
async def join_waitlist(body: WaitlistRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WaitlistEntry).where(WaitlistEntry.email == body.email))
    if result.scalar_one_or_none() is not None:
        return {"message": "Email já cadastrado na waitlist"}

    entry = WaitlistEntry(email=body.email)
    db.add(entry)
    await db.commit()
    return {"message": "Adicionado à waitlist com sucesso"}
