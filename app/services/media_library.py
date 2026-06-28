"""Local media library for pre-loaded video clips (gameplay, satisfying, etc.)."""

import logging
import random
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

LIBRARY_DIR = settings.STORAGE_DIR / "library"


def list_clips(tag: str) -> list[Path]:
    """List all clips for a given library tag."""
    tag_dir = LIBRARY_DIR / tag
    if not tag_dir.exists():
        logger.warning(f"Library tag '{tag}' not found at {tag_dir}")
        return []
    clips = sorted(tag_dir.glob("*.mp4"))
    logger.info(f"Library '{tag}': {len(clips)} clips available")
    return clips


def pick_clip(tag: str) -> Path | None:
    """Pick a random clip: local library first, then Google Drive (rclone cache)."""
    clips = list_clips(tag)
    if clips:
        return random.choice(clips)
    try:
        from app.services.drive_library import pick_drive_clip

        return pick_drive_clip(tag)
    except Exception as e:  # noqa: BLE001 — Drive e opcional; degrada para "sem clip"
        logger.warning("drive_library indisponivel para '%s': %s", tag, e)
        return None


def count_clips(tag: str) -> int:
    """Total de clips para a tag: pasta local + indice do Drive."""
    local = len(list_clips(tag))
    try:
        from app.services.drive_library import count_for_tag

        return local + count_for_tag(tag)
    except Exception:  # noqa: BLE001
        return local
