from app.config import Settings


def test_settings_defaults():
    s = Settings(ANTHROPIC_API_KEY="k", PEXELS_API_KEY="k")
    assert s.VIDEO_WIDTH == 1080
    assert s.VIDEO_HEIGHT == 1920
    assert s.REDIS_URL == "redis://localhost:6379/0"
