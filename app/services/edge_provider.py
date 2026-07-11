"""Edge TTS provider — free Microsoft voices for pt-BR."""

import logging
from pathlib import Path

import edge_tts

from app.config import settings
from app.services.tts import _fit_to_duration
from app.services.voice_provider import VoiceInfo, VoiceProvider

logger = logging.getLogger(__name__)

# preview_url: MP3s estaticos em frontend/public/voice-previews (gerados 1x com os
# defaults do produto, rate -10% pitch +5Hz) — o play da aba Voz nao gasta TTS.
EDGE_VOICES = [
    VoiceInfo(
        id="pt-BR-AntonioNeural",
        name="Antonio",
        provider="edge",
        language="pt-BR",
        gender="male",
        preview_url="/voice-previews/pt-BR-AntonioNeural.mp3",
    ),
    VoiceInfo(
        id="pt-BR-FranciscaNeural",
        name="Francisca",
        provider="edge",
        language="pt-BR",
        gender="female",
        preview_url="/voice-previews/pt-BR-FranciscaNeural.mp3",
    ),
    VoiceInfo(
        id="pt-BR-ThalitaMultilingualNeural",
        name="Thalita",
        provider="edge",
        language="pt-BR",
        gender="female",
        preview_url="/voice-previews/pt-BR-ThalitaMultilingualNeural.mp3",
    ),
]


class EdgeTTSProvider(VoiceProvider):
    provider_name = "edge"

    async def synthesize(
        self,
        text: str,
        output_path: str,
        voice_id: str = "pt-BR-AntonioNeural",
        rate: int = -10,
        pitch: int = 5,
        duration_target: float = 0,
        **kwargs,
    ) -> Path:
        communicate = edge_tts.Communicate(
            text,
            voice_id,
            rate=f"{rate:+d}%",
            pitch=f"{pitch:+d}Hz",
        )
        await communicate.save(output_path)

        if duration_target > 0:
            _fit_to_duration(output_path, duration_target)

        return Path(output_path)

    async def list_voices(self) -> list[VoiceInfo]:
        return EDGE_VOICES

    def estimate_cost(self, text: str) -> int:
        return settings.CREDIT_COST_EDGE
