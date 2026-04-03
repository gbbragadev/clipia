import uuid
from pathlib import Path

import redis
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import settings
from app.models import GenerateRequest, JobStatus
from app.worker.tasks import dispatch_pipeline

router = APIRouter()
_redis = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


@router.post("/generate")
def generate(req: GenerateRequest):
    job_id = str(uuid.uuid4())
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
    return FileResponse(str(file_path), media_type="video/mp4", filename=f"short_{job_id}.mp4")
