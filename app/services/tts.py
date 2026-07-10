import asyncio
import json
import logging
import shutil
import subprocess

import edge_tts

VOICE = "pt-BR-AntonioNeural"
RATE = "-10%"
PITCH = "+5Hz"
SUPPORTED_VOICE_IDS = (
    "pt-BR-AntonioNeural",
    "pt-BR-FranciscaNeural",
)

logger = logging.getLogger(__name__)


def synthesize_narration(
    text: str,
    output_path: str,
    speaker_wav: str = "",
    duration_target: float = 0,
    voice_id: str = "pt-BR-AntonioNeural",
    rate: int = -10,
    pitch: int = 5,
) -> str:
    """Generate narration with natural prosody using Edge TTS (sync — for Celery worker)."""
    asyncio.run(_generate(text, output_path, voice_id, rate, pitch))

    if duration_target > 0:
        _fit_to_duration(output_path, duration_target)

    return output_path


async def synthesize_narration_async(
    text: str,
    output_path: str,
    speaker_wav: str = "",
    duration_target: float = 0,
    voice_id: str = "pt-BR-AntonioNeural",
    rate: int = -10,
    pitch: int = 5,
) -> str:
    """Generate narration with natural prosody using Edge TTS (async — for FastAPI)."""
    await _generate(text, output_path, voice_id, rate, pitch)

    if duration_target > 0:
        _fit_to_duration(output_path, duration_target)

    return output_path


def _fit_to_duration(audio_path: str, target: float) -> None:
    """Pad or trim audio to match target duration exactly."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", audio_path],
        capture_output=True,
        text=True,
        timeout=10,
    )
    duration = float(json.loads(result.stdout)["format"]["duration"])

    if abs(duration - target) <= 0.5:
        return  # close enough

    fitted_path = audio_path + ".fitted.wav"

    if duration < target:
        # Pad with silence at the end
        pad_seconds = target - duration
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                audio_path,
                "-af",
                f"apad=pad_dur={pad_seconds}",
                "-c:a",
                "pcm_s16le",
                fitted_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        logger.info(f"Padded audio from {duration:.1f}s to {target:.1f}s (+{pad_seconds:.1f}s silence)")
    else:
        # Trim with fade out at the end
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                audio_path,
                "-t",
                str(target),
                "-af",
                f"afade=t=out:st={target - 1}:d=1",
                "-c:a",
                "pcm_s16le",
                fitted_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        logger.info(f"Trimmed audio from {duration:.1f}s to {target:.1f}s (-{duration - target:.1f}s)")

    shutil.move(fitted_path, audio_path)


async def _generate(
    text: str, output_path: str, voice_id: str = "pt-BR-AntonioNeural", rate: int = -10, pitch: int = 5
) -> None:
    communicate = edge_tts.Communicate(
        text,
        voice_id,
        rate=f"{rate:+d}%",
        pitch=f"{pitch:+d}Hz",
    )
    await communicate.save(output_path)
