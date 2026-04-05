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


def path_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file() or path.is_symlink():
        return path.stat().st_size

    total = 0
    for child in path.rglob("*"):
        if child.is_file() and not child.is_symlink():
            total += child.stat().st_size
    return total


def remove_path(path: Path) -> int:
    """Remove a file or directory and return the bytes reclaimed."""
    size = path_size_bytes(path)
    if not path.exists():
        return 0
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    return size


def bytes_to_gb(value: int) -> float:
    return round(value / (1024**3), 4)
