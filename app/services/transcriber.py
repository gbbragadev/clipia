"""Audio transcription via Groq Whisper API (Phase A: remote ASR only).

Exposes the same public surface as the former local-Whisper implementation:

    transcribe_with_timestamps(audio_path: str) -> list[dict]

Each item: {"word": str, "start": float, "end": float}.
"""

import logging
import time
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

_BACKOFF_SECONDS = (2, 4, 8)  # 3 attempts total
_NON_RETRYABLE_STATUS = frozenset({400, 401, 403, 404, 422})


def _get_groq_client():
    from groq import Groq

    if not settings.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not configured")
    return Groq(api_key=settings.GROQ_API_KEY)


def _get_openai_client():
    from openai import OpenAI

    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not configured")
    return OpenAI(api_key=settings.OPENAI_API_KEY)


def _transcribe_groq(audio_path: str) -> list[dict]:
    client = _get_groq_client()
    with open(audio_path, "rb") as f:
        response = client.audio.transcriptions.create(
            file=(Path(audio_path).name, f.read()),
            model=settings.GROQ_WHISPER_MODEL,
            language="pt",
            response_format="verbose_json",
            timestamp_granularities=["word"],
        )
    return _parse_response_words(response)


def _transcribe_openai(audio_path: str) -> list[dict]:
    client = _get_openai_client()
    with open(audio_path, "rb") as f:
        response = client.audio.transcriptions.create(
            file=f,
            model=settings.OPENAI_WHISPER_MODEL,
            language="pt",
            response_format="verbose_json",
            timestamp_granularities=["word"],
        )
    return _parse_response_words(response)


def _parse_response_words(response) -> list[dict]:
    """Normalize Groq/OpenAI verbose_json word-level response to our schema."""
    raw_words = getattr(response, "words", None) or []
    words = []
    for w in raw_words:
        text_clean = w.word.strip()
        if text_clean:
            words.append(
                {
                    "word": text_clean,
                    "start": round(float(w.start), 3),
                    "end": round(float(w.end), 3),
                }
            )
    if not words:
        raise RuntimeError("empty transcription: no word-level timestamps returned")
    return words


def transcribe_with_timestamps(audio_path: str) -> list[dict]:
    """Transcribe audio file to word-level timestamps.

    Tries Groq first. If ASR_FALLBACK_ENABLED and Groq exhausts retries,
    tries OpenAI Whisper as fallback before raising.
    """
    last_exc: Exception | None = None
    for attempt, backoff in enumerate(_BACKOFF_SECONDS, start=1):
        try:
            words = _transcribe_groq(audio_path)
            if attempt > 1:
                logger.info("Groq transcription succeeded on attempt %d", attempt)
            return words
        except RuntimeError:
            # empty transcription, missing key — do not retry
            raise
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            if status in _NON_RETRYABLE_STATUS:
                logger.warning("Groq returned non-retryable %s: %s", status, exc)
                raise
            last_exc = exc
            logger.warning(
                "Groq transcription attempt %d/%d failed: %s",
                attempt,
                len(_BACKOFF_SECONDS),
                exc,
            )
            if attempt < len(_BACKOFF_SECONDS):
                time.sleep(backoff)

    if settings.ASR_FALLBACK_ENABLED:
        logger.warning("Groq exhausted retries; falling back to OpenAI Whisper")
        try:
            return _transcribe_openai(audio_path)
        except Exception as exc:
            logger.error("OpenAI Whisper fallback also failed: %s", exc)
            raise

    if last_exc is None:
        raise RuntimeError("Groq retry loop exited without capturing an error")
    raise last_exc
