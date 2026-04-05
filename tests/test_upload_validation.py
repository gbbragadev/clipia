import pytest
from app.api.routes import _validate_audio_upload

def test_rejects_non_audio_mime():
    with pytest.raises(ValueError, match="audio"):
        _validate_audio_upload(content_type="application/pdf", filename="virus.pdf", size=1000)

def test_rejects_oversized_file():
    with pytest.raises(ValueError, match="grande"):
        _validate_audio_upload(content_type="audio/wav", filename="big.wav", size=60 * 1024 * 1024)

def test_accepts_valid_wav():
    ext = _validate_audio_upload(content_type="audio/wav", filename="test.wav", size=5000)
    assert ext == ".wav"

def test_accepts_valid_mp3():
    ext = _validate_audio_upload(content_type="audio/mpeg", filename="test.mp3", size=5000)
    assert ext == ".mp3"

def test_accepts_valid_webm():
    ext = _validate_audio_upload(content_type="audio/webm", filename="test.webm", size=5000)
    assert ext == ".webm"

def test_sanitizes_extension():
    ext = _validate_audio_upload(content_type="audio/wav", filename="../../../etc/passwd", size=5000)
    assert ext == ".wav"

def test_rejects_executable_disguised():
    with pytest.raises(ValueError):
        _validate_audio_upload(content_type="application/x-executable", filename="audio.wav", size=5000)

def test_handles_none_content_type():
    with pytest.raises(ValueError):
        _validate_audio_upload(content_type=None, filename="audio.wav", size=5000)
