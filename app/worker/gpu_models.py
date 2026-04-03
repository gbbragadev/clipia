from threading import Lock

_tts_model = None
_whisper_model = None
_lock = Lock()


def get_tts_model():
    global _tts_model
    if _tts_model is None:
        with _lock:
            if _tts_model is None:
                from TTS.api import TTS
                _tts_model = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cuda")
    return _tts_model


def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        with _lock:
            if _whisper_model is None:
                from faster_whisper import WhisperModel
                from app.config import settings
                _whisper_model = WhisperModel(
                    settings.WHISPER_MODEL_SIZE,
                    device=settings.DEVICE,
                    compute_type=settings.WHISPER_COMPUTE_TYPE,
                )
    return _whisper_model
