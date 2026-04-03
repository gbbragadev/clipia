from unittest.mock import MagicMock, patch

from app.services.tts import synthesize_narration


def test_synthesize_narration_calls_tts():
    mock_tts = MagicMock()
    with patch("app.services.tts.get_tts_model", return_value=mock_tts):
        result = synthesize_narration(
            text="Teste de narracao.",
            output_path="/tmp/test_narration.wav",
            speaker_wav="/tmp/ref.wav",
        )
    mock_tts.tts_to_file.assert_called_once_with(
        text="Teste de narracao.",
        speaker_wav="/tmp/ref.wav",
        language="pt",
        file_path="/tmp/test_narration.wav",
    )
    assert result == "/tmp/test_narration.wav"
