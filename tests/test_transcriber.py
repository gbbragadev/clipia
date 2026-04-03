from unittest.mock import MagicMock, patch

from app.services.transcriber import transcribe_with_timestamps


def test_transcribe_returns_word_timestamps():
    mock_word1 = MagicMock(word=" Voce ", start=0.0, end=0.3)
    mock_word2 = MagicMock(word=" sabia ", start=0.3, end=0.7)
    mock_segment = MagicMock(words=[mock_word1, mock_word2])
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([mock_segment], MagicMock())

    with patch("app.services.transcriber.get_whisper_model", return_value=mock_model):
        words = transcribe_with_timestamps("/tmp/audio.wav")

    assert len(words) == 2
    assert words[0]["word"] == "Voce"
    assert words[0]["start"] == 0.0
    assert words[1]["word"] == "sabia"
