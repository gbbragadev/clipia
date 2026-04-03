import shutil
from pathlib import Path

from app.config import settings


def get_job_dir(job_id: str) -> Path:
    job_dir = settings.STORAGE_DIR / "jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    return job_dir


def get_output_dir() -> Path:
    out_dir = settings.STORAGE_DIR / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def cleanup_job_dir(job_id: str) -> None:
    job_dir = settings.STORAGE_DIR / "jobs" / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir)
