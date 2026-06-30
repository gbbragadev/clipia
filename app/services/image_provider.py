"""OpenAI gpt-image-2 provider with SHA-256 cache and retry policy."""

from __future__ import annotations

import base64
import hashlib
import logging
import shutil
import time
from pathlib import Path

from openai import APIStatusError, APITimeoutError, BadRequestError, OpenAI

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
        model: str | None = None,
        quality: str | None = None,
        size: str = "1024x1536",
        moderation: str | None = None,
        cache_dir: Path | None = None,
        max_retries: int = 3,
        timeout_s: float = 60.0,
    ) -> None:
        # Usa a chave do LLM (sk-proj, validada na cascata) por padrao; a OPENAI_API_KEY antiga
        # estava dando 401 em gpt-image. Fallback p/ ela se LLM_OPENAI_KEY nao estiver setada.
        self.api_key = api_key or settings.LLM_OPENAI_KEY or settings.OPENAI_API_KEY
        self.model = model or settings.GPT_IMAGE_MODEL
        self.quality = quality or settings.GPT_IMAGE_QUALITY
        self.size = size
        self.moderation = moderation or settings.GPT_IMAGE_MODERATION
        self.cache_dir = cache_dir or (settings.STORAGE_DIR / "image-cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_retries = max_retries
        self.timeout_s = timeout_s

    def _client(self) -> OpenAI:
        return OpenAI(api_key=self.api_key, timeout=self.timeout_s)

    def _cache_key(self, prompt: str) -> str:
        raw = f"{self.model}|{prompt}|{self.size}|{self.quality}|{self.moderation}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def generate(self, prompt: str, output_path: Path) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cache_file = self.cache_dir / f"{self._cache_key(prompt)}.png"
        if cache_file.exists():
            logger.info("Image cache HIT for prompt=%s", prompt[:60])
            shutil.copy(cache_file, output_path)
            return output_path

        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
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
                cache_file.write_bytes(png_bytes)
                shutil.copy(cache_file, output_path)
                return output_path
            except BadRequestError as e:
                msg = str(e).lower()
                if "moderation" in msg or "content_policy" in msg or "safety" in msg:
                    raise ModerationBlockedError(f"cena bloqueada pela moderação: {prompt[:80]}") from e
                raise
            except (APIStatusError, APITimeoutError) as e:
                last_exc = e
                if attempt < self.max_retries - 1:
                    backoff = 2**attempt
                    logger.warning(
                        "Image API error (attempt %d/%d), sleeping %ds: %s",
                        attempt + 1,
                        self.max_retries,
                        backoff,
                        e,
                    )
                    time.sleep(backoff)

        raise ImageProviderError(f"max_retries={self.max_retries} esgotado: {last_exc}") from last_exc
