from app.worker.gpu_models import get_tts_model


def synthesize_narration(text: str, output_path: str, speaker_wav: str) -> str:
    tts = get_tts_model()
    tts.tts_to_file(
        text=text,
        speaker_wav=speaker_wav,
        language="pt",
        file_path=output_path,
    )
    return output_path
