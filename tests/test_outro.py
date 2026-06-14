from app.config import settings


def test_outro_settings_defaults():
    assert settings.OUTRO_ENABLED is True
    assert settings.OUTRO_DURATION == 1.5
    assert settings.OUTRO_BLUR_SIGMA == 16.0
    assert settings.OUTRO_DARKEN == 0.30
    assert settings.OUTRO_LOGO_WIDTH == 520
    assert str(settings.OUTRO_AUDIO_PATH).replace("\\", "/").endswith("app/assets/outro/whisper.wav")
    assert str(settings.OUTRO_LOGO_PATH).replace("\\", "/").endswith("app/assets/outro/logo.png")
