import pytest

from app.job_config import resolve_job_flag


class _StubRedis:
    def __init__(self, fields):
        self._fields = fields

    def hget(self, key, field):
        return self._fields.get(field)


def test_resolve_job_flag_reads_overrides():
    r = _StubRedis({"sfx_enabled": "1", "music_enabled": "0"})
    assert resolve_job_flag(r, "job1", "sfx_enabled", default=False) is True
    assert resolve_job_flag(r, "job1", "music_enabled", default=True) is False


def test_resolve_job_flag_falls_back_to_default_when_absent():
    r = _StubRedis({})
    assert resolve_job_flag(r, "job1", "sfx_enabled", default=True) is True
    assert resolve_job_flag(r, "job1", "sfx_enabled", default=False) is False


def test_resolve_job_flag_handles_bytes():
    r = _StubRedis({"sfx_enabled": b"0"})
    assert resolve_job_flag(r, "job1", "sfx_enabled", default=True) is False


@pytest.mark.asyncio
async def test_generate_persists_audio_flags_in_redis(client, app, verified_user, auth_headers):
    resp = await client.post(
        "/api/v1/generate",
        json={
            "topic": "cinco curiosidades sobre o oceano profundo",
            "style": "educational",
            "duration_target": 30,
            "template_id": "stock_narration",
            "voice_provider": "edge",
            "sfx_enabled": False,
            "music_enabled": True,
        },
        headers=auth_headers(verified_user),
    )
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]
    assert app.state.fake_redis.hget(f"job:{job_id}", "sfx_enabled") == "0"
    assert app.state.fake_redis.hget(f"job:{job_id}", "music_enabled") == "1"


@pytest.mark.asyncio
async def test_generate_without_flags_leaves_them_absent(client, app, verified_user, auth_headers):
    resp = await client.post(
        "/api/v1/generate",
        json={
            "topic": "cinco curiosidades sobre o oceano profundo",
            "style": "educational",
            "duration_target": 30,
            "template_id": "stock_narration",
            "voice_provider": "edge",
        },
        headers=auth_headers(verified_user),
    )
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]
    assert app.state.fake_redis.hget(f"job:{job_id}", "sfx_enabled") is None


def test_dialogue_voices_are_not_legacy_en():
    from app.config import settings

    legacy = {"21m00Tcm4TlvDq8ikWAM", "pNInz6obpgDQGcFmaJgB"}  # Rachel / Adam (EN)
    assert settings.DIALOGUE_VOICE_A not in legacy
    assert settings.DIALOGUE_VOICE_B not in legacy


def test_dialogue_template_uses_configured_voice():
    from app.config import settings
    from app.templates import get_template

    assert get_template("dialogue_duo").voice.voice_id == settings.DIALOGUE_VOICE_A
