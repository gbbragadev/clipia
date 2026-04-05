"""Voice provider abstraction — unified interface for TTS engines."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class VoiceInfo:
    id: str
    name: str
    provider: str  # "edge", "elevenlabs", "custom"
    language: str
    gender: str | None = None
    preview_url: str | None = None
    is_clone: bool = False


class VoiceProvider(ABC):
    """Abstract base for all voice/TTS providers."""

    provider_name: str = ""

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        output_path: str,
        voice_id: str,
        **kwargs,
    ) -> Path:
        """Generate audio from text. Returns path to WAV file."""

    @abstractmethod
    async def list_voices(self) -> list[VoiceInfo]:
        """Return available voices for this provider."""

    @abstractmethod
    def estimate_cost(self, text: str) -> int:
        """Estimate credit cost for synthesizing this text."""


def get_voice_provider(provider_name: str) -> VoiceProvider:
    """Factory — returns the right provider instance by name."""
    if provider_name == "edge":
        from app.services.edge_provider import EdgeTTSProvider

        return EdgeTTSProvider()
    elif provider_name == "elevenlabs":
        from app.services.elevenlabs_provider import ElevenLabsProvider

        return ElevenLabsProvider()
    elif provider_name == "custom":
        from app.services.custom_audio_provider import CustomAudioProvider

        return CustomAudioProvider()
    else:
        raise ValueError(f"Unknown voice provider: {provider_name}")
