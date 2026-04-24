"""OpenAI gpt-image-2 provider with SHA-256 cache and retry policy."""

from __future__ import annotations

import logging
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)


class ModerationBlockedError(Exception):
    """Raised when OpenAI content moderation blocks the prompt."""


class ImageProviderError(Exception):
    """Raised after retries are exhausted on transient failures."""


class OpenAIImageProvider:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-image-2",
        quality: str | None = None,
        size: str = "1024x1536",
        moderation: str = "low",
        cache_dir: Path | None = None,
        max_retries: int = 3,
        timeout_s: float = 60.0,
    ) -> None:
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model
        self.quality = quality or settings.GPT_IMAGE_QUALITY
        self.size = size
        self.moderation = moderation
        self.cache_dir = cache_dir or (settings.STORAGE_DIR / "image-cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_retries = max_retries
        self.timeout_s = timeout_s

    def generate(self, prompt: str, output_path: Path) -> Path:
        raise NotImplementedError("implemented in Task 3")
