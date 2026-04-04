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
    """Pick a random clip from the library for a given tag."""
    clips = list_clips(tag)
    if not clips:
        return None
    return random.choice(clips)
