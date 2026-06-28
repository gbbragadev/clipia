"""Síntese de diálogo multi-locutor via ElevenLabs text_to_dialogue.

Recebe as cenas do roteiro (cada uma com speaker 'A'/'B' + text) e sintetiza UM áudio com as
duas vozes alternando, como uma conversa. Reusa o client/conversão PCM→WAV do provider de voz.
"""

import logging
import subprocess
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)


def build_dialogue_inputs(scenes: list[dict], voice_a: str, voice_b: str) -> list[dict]:
    """scenes[].speaker ('A'/'B') + text -> lista [{text, voice_id}] para text_to_dialogue."""
    inputs: list[dict] = []
    for sc in scenes:
        text = (sc.get("text") or "").strip()
        if not text:
            continue
        speaker = (sc.get("speaker") or "A").upper()
        inputs.append({"text": text, "voice_id": voice_b if speaker == "B" else voice_a})
    return inputs


def synthesize_dialogue(
    scenes: list[dict],
    output_path: str,
    voice_a: str | None = None,
    voice_b: str | None = None,
    duration_target: float = 0,
) -> str:
    from app.services.elevenlabs_provider import _get_client
    from app.services.tts import _fit_to_duration

    inputs = build_dialogue_inputs(scenes, voice_a or settings.DIALOGUE_VOICE_A, voice_b or settings.DIALOGUE_VOICE_B)
    if not inputs:
        raise RuntimeError("diálogo sem falas")

    client = _get_client()
    audio = client.text_to_dialogue.convert(inputs=inputs, output_format="pcm_24000")

    pcm_path = output_path + ".pcm"
    with open(pcm_path, "wb") as f:
        for chunk in audio:
            f.write(chunk)
    subprocess.run(
        ["ffmpeg", "-y", "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", pcm_path, "-c:a", "pcm_s16le", output_path],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    Path(pcm_path).unlink(missing_ok=True)

    if duration_target > 0:
        _fit_to_duration(output_path, duration_target)

    logger.info("Diálogo: %d falas sintetizadas → %s", len(inputs), output_path)
    return output_path
