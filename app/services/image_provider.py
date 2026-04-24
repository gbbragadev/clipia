"""OpenAI gpt-image-2 provider with SHA-256 cache and retry policy."""

from __future__ import annotations

import base64
import hashlib
import logging
from pathlib import Path

from openai import OpenAI

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

    def _client(self) -> OpenAI:
        return OpenAI(api_key=self.api_key, timeout=self.timeout_s)

    def _cache_key(self, prompt: str) -> str:
        raw = f"{prompt}|{self.size}|{self.quality}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def generate(self, prompt: str, output_path: Path) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        resp = self._client().images.generate(
            model=self.model,
            prompt=prompt,
            size=self.size,
            quality=self.quality,
            moderation=self.moderation,
            n=1,
        )
        b64 = resp.data[0].b64_json
        png_bytes = base64.b64decode(b64)
        output_path.write_bytes(png_bytes)
        return output_path
