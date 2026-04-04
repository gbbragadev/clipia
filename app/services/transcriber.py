import ctypes
import os

# Pre-load CUDA libs before ctranslate2 tries to find them
_CUDA_LIB_DIR = "/usr/local/lib/ollama/cuda_v12"
for lib_name in ["libcublas.so.12", "libcublasLt.so.12", "libcudnn.so.9"]:
    lib_path = os.path.join(_CUDA_LIB_DIR, lib_name)
    if os.path.exists(lib_path):
        try:
            ctypes.cdll.LoadLibrary(lib_path)
        except OSError:
            pass

from app.worker.gpu_models import get_whisper_model


def transcribe_with_timestamps(audio_path: str) -> list[dict]:
    model = get_whisper_model()
    segments, _info = model.transcribe(
        audio_path,
        language="pt",
        beam_size=5,
        word_timestamps=True,
        vad_filter=True,
    )
    words = []
    for segment in segments:
        for word in segment.words:
            words.append({
                "word": word.word.strip(),
                "start": round(word.start, 3),
                "end": round(word.end, 3),
            })
    return words
