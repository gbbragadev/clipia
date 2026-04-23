"""Tests for app.services.transcriber (Phase A: Groq API backend)."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.transcriber import transcribe_with_timestamps


def _groq_response_with_words():
    """Minimal mock of Groq verbose_json response."""
    resp = MagicMock()
    resp.words = [
        MagicMock(word="Voce", start=0.0, end=0.3),
        MagicMock(word="sabia", start=0.3, end=0.7),
        MagicMock(word="disso", start=0.7, end=1.1),
    ]
    return resp


def test_transcribe_returns_word_timestamps(tmp_path):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"fake wav")

    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = _groq_response_with_words()

    with patch("app.services.transcriber._get_groq_client", return_value=mock_client):
        words = transcribe_with_timestamps(str(audio))

    assert len(words) == 3
    assert words[0] == {"word": "Voce", "start": 0.0, "end": 0.3}
    assert words[1] == {"word": "sabia", "start": 0.3, "end": 0.7}
    assert words[2] == {"word": "disso", "start": 0.7, "end": 1.1}


def test_transcribe_strips_whitespace_from_words(tmp_path):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"fake wav")

    resp = MagicMock()
    resp.words = [MagicMock(word="  hello  ", start=0.0, end=0.5)]
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = resp

    with patch("app.services.transcriber._get_groq_client", return_value=mock_client):
        words = transcribe_with_timestamps(str(audio))

    assert words[0]["word"] == "hello"


def test_transcribe_raises_when_groq_returns_no_words(tmp_path):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"fake wav")

    resp = MagicMock()
    resp.words = []
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = resp

    with patch("app.services.transcriber._get_groq_client", return_value=mock_client):
        with pytest.raises(RuntimeError, match="empty transcription"):
            transcribe_with_timestamps(str(audio))


def test_transcribe_retries_on_transient_error_then_succeeds(tmp_path, monkeypatch):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"fake wav")

    mock_client = MagicMock()
    call = {"n": 0}

    def _side_effect(**_kwargs):
        call["n"] += 1
        if call["n"] < 3:
            raise ConnectionError("boom")
        return _groq_response_with_words()

    mock_client.audio.transcriptions.create.side_effect = _side_effect
    # Zero backoff for test speed
    monkeypatch.setattr("app.services.transcriber._BACKOFF_SECONDS", (0, 0, 0))

    with patch("app.services.transcriber._get_groq_client", return_value=mock_client):
        words = transcribe_with_timestamps(str(audio))

    assert call["n"] == 3
    assert len(words) == 3


def test_transcribe_raises_after_max_retries(tmp_path, monkeypatch):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"fake wav")

    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.side_effect = ConnectionError("boom")
    monkeypatch.setattr("app.services.transcriber._BACKOFF_SECONDS", (0, 0, 0))

    with patch("app.services.transcriber._get_groq_client", return_value=mock_client):
        with pytest.raises(ConnectionError):
            transcribe_with_timestamps(str(audio))


def test_openai_fallback_activates_when_groq_fails_and_flag_enabled(tmp_path, monkeypatch):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"fake wav")

    groq_client = MagicMock()
    groq_client.audio.transcriptions.create.side_effect = ConnectionError("groq down")

    openai_client = MagicMock()
    openai_client.audio.transcriptions.create.return_value = _groq_response_with_words()

    monkeypatch.setattr("app.services.transcriber._BACKOFF_SECONDS", (0, 0, 0))
    monkeypatch.setattr("app.config.settings.ASR_FALLBACK_ENABLED", True)

    with (
        patch("app.services.transcriber._get_groq_client", return_value=groq_client),
        patch("app.services.transcriber._get_openai_client", return_value=openai_client),
    ):
        words = transcribe_with_timestamps(str(audio))

    assert len(words) == 3
    assert openai_client.audio.transcriptions.create.called


def test_openai_fallback_skipped_when_flag_disabled(tmp_path, monkeypatch):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"fake wav")

    groq_client = MagicMock()
    groq_client.audio.transcriptions.create.side_effect = ConnectionError("groq down")
    openai_client = MagicMock()

    monkeypatch.setattr("app.services.transcriber._BACKOFF_SECONDS", (0, 0, 0))
    monkeypatch.setattr("app.config.settings.ASR_FALLBACK_ENABLED", False)

    with (
        patch("app.services.transcriber._get_groq_client", return_value=groq_client),
        patch("app.services.transcriber._get_openai_client", return_value=openai_client),
    ):
        with pytest.raises(ConnectionError):
            transcribe_with_timestamps(str(audio))

    assert not openai_client.audio.transcriptions.create.called
