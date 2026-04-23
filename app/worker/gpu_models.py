"""GPU-bound model loaders.

Phase A (Windows pivot): local ASR (Whisper via faster-whisper) and local
TTS (XTTS via TTS) are disabled. Transcription runs via Groq API, TTS via
ElevenLabs/EdgeTTS. These functions are kept as shells so that future phases
can re-enable local models without re-plumbing callers.
"""

from threading import Lock

_tts_model = None
_whisper_model = None
_lock = Lock()


def get_tts_model():
    raise NotImplementedError("Local XTTS TTS disabled in Phase A. Use ElevenLabsProvider or EdgeProvider.")


def get_whisper_model():
    raise NotImplementedError(
        "Local faster-whisper disabled in Phase A. Use app.services.transcriber " "(Groq API) instead."
    )
