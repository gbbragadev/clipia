"""Custom audio provider — user-uploaded audio files."""

import json
import logging
import subprocess
from pathlib import Path

from app.credits import CREDIT_TARIFFS
from app.services.voice_provider import VoiceInfo, VoiceProvider

logger = logging.getLogger(__name__)

# Limits
MAX_DURATION_SECONDS = 180
MIN_DURATION_SECONDS = 5
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB


class CustomAudioProvider(VoiceProvider):
    provider_name = "custom"

    async def synthesize(
        self,
        text: str,
        output_path: str,
        voice_id: str,
        **kwargs,
    ) -> Path:
        """Reject arbitrary local sources; uploads belong to an authenticated job route."""
        raise RuntimeError("Custom synthesis paths are disabled; upload audio to an owned job")

    async def list_voices(self) -> list[VoiceInfo]:
        return [
            VoiceInfo(
                id="custom_upload",
                name="Minha voz (upload)",
                provider="custom",
                language="any",
            ),
        ]

    def estimate_cost(self, text: str) -> int:
        return int(CREDIT_TARIFFS.standard_voice)


def validate_audio_file(file_path: str) -> dict:
    """Validate uploaded audio. Returns metadata or raises ValueError."""
    path = Path(file_path)
    if not path.exists():
        raise ValueError("Arquivo não encontrado")

    size = path.stat().st_size
    if size > MAX_FILE_SIZE_BYTES:
        raise ValueError(
            f"Arquivo muito grande ({size / 1024 / 1024:.1f}MB, máximo {MAX_FILE_SIZE_BYTES // 1024 // 1024}MB)"
        )

    # Probe with ffprobe
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            file_path,
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise ValueError("Formato de áudio não reconhecido")

    info = json.loads(result.stdout)
    duration = float(info.get("format", {}).get("duration", 0))

    if duration < MIN_DURATION_SECONDS:
        raise ValueError(f"Áudio muito curto ({duration:.1f}s, mínimo {MIN_DURATION_SECONDS}s)")
    if duration > MAX_DURATION_SECONDS:
        raise ValueError(f"Áudio muito longo ({duration:.1f}s, máximo {MAX_DURATION_SECONDS}s)")

    return {"duration": duration, "size_bytes": size, "format": info.get("format", {}).get("format_name", "unknown")}


def normalize_audio(input_path: str, output_path: str) -> None:
    """Convert any audio format to standard WAV (16-bit, 24kHz, mono)."""
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            input_path,
            "-ar",
            "24000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            output_path,
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    logger.info(f"Normalized audio: {input_path} → {output_path}")
