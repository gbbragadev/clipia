"""ElevenLabs TTS provider — premium voices with cloning support."""

import json
import logging
from pathlib import Path

from app.config import settings
from app.redis_pool import get_redis
from app.services.tts import _fit_to_duration
from app.services.voice_provider import VoiceInfo, VoiceProvider

logger = logging.getLogger(__name__)

# Cache voices in Redis for 24h to avoid hammering the API
_VOICES_CACHE_KEY = "elevenlabs:voices_cache"
_VOICES_CACHE_TTL = 86400  # 24h


def _get_client():
    from elevenlabs import ElevenLabs

    if not settings.ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY not configured")
    return ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)


class ElevenLabsProvider(VoiceProvider):
    provider_name = "elevenlabs"

    async def synthesize(
        self,
        text: str,
        output_path: str,
        voice_id: str,
        duration_target: float = 0,
        model_id: str = "eleven_multilingual_v2",
        **kwargs,
    ) -> Path:
        client = _get_client()

        # Stream audio chunks to file
        audio_iter = client.text_to_speech.convert(
            voice_id=voice_id,
            text=text,
            model_id=model_id,
            output_format="pcm_24000",
            language_code="pt",
        )

        # Write raw PCM, then wrap as WAV
        pcm_path = output_path + ".pcm"
        with open(pcm_path, "wb") as f:
            for chunk in audio_iter:
                f.write(chunk)

        # Convert PCM to WAV via ffmpeg
        import subprocess

        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "s16le",
                "-ar",
                "24000",
                "-ac",
                "1",
                "-i",
                pcm_path,
                "-c:a",
                "pcm_s16le",
                output_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        Path(pcm_path).unlink(missing_ok=True)

        if duration_target > 0:
            _fit_to_duration(output_path, duration_target)

        size_kb = Path(output_path).stat().st_size / 1024
        logger.info(f"ElevenLabs TTS: {len(text)} chars → {size_kb:.0f}KB WAV (voice={voice_id})")
        return Path(output_path)

    async def list_voices(self) -> list[VoiceInfo]:
        r = get_redis()

        # Try cache first
        cached = r.get(_VOICES_CACHE_KEY)
        if cached:
            return [VoiceInfo(**v) for v in json.loads(cached)]

        # Fetch from API
        client = _get_client()
        response = client.voices.get_all()
        voices = []
        for v in response.voices:
            voices.append(
                VoiceInfo(
                    id=v.voice_id,
                    name=v.name,
                    provider="elevenlabs",
                    language="multilingual",
                    gender=v.labels.get("gender") if v.labels else None,
                    preview_url=v.preview_url,
                    is_clone=v.category == "cloned",
                )
            )

        # Cache for 24h
        r.set(_VOICES_CACHE_KEY, json.dumps([v.__dict__ for v in voices]), ex=_VOICES_CACHE_TTL)
        return voices

    def estimate_cost(self, text: str) -> int:
        return settings.CREDIT_COST_ELEVENLABS

    async def design_voice(self, name: str, description: str, text: str | None = None) -> str:
        """Design a voice from a text description (Voice Design). Returns the new voice_id.

        One-shot: gera previews a partir da descrição e cria a voz com o primeiro preview.
        """
        client = _get_client()
        design = client.text_to_voice.design(
            voice_description=description,
            text=text,
            auto_generate_text=text is None,
        )
        previews = getattr(design, "previews", None) or []
        if not previews:
            raise RuntimeError("Voice Design não retornou previews")

        voice = client.text_to_voice.create(
            voice_name=name,
            voice_description=description,
            generated_voice_id=previews[0].generated_voice_id,
        )

        get_redis().delete(_VOICES_CACHE_KEY)  # nova voz aparece em list_voices
        logger.info("Voice Design: '%s' → %s", name, voice.voice_id)
        return voice.voice_id

    async def clone_voice(self, name: str, audio_files: list[bytes], description: str = "") -> str:
        """Clone a voice from audio samples. Returns the new voice_id."""
        client = _get_client()
        response = client.voices.ivc.create(
            name=name,
            files=audio_files,
            description=description or f"ClipIA clone: {name}",
        )

        # Invalidate voices cache
        get_redis().delete(_VOICES_CACHE_KEY)

        logger.info(f"Voice cloned: {name} → {response.voice_id}")
        return response.voice_id

    async def delete_voice(self, voice_id: str) -> None:
        """Delete a cloned voice from ElevenLabs."""
        client = _get_client()
        client.voices.delete(voice_id=voice_id)

        get_redis().delete(_VOICES_CACHE_KEY)

        logger.info(f"Voice deleted: {voice_id}")
