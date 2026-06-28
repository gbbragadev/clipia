import json as _json

import pytest

from app.services import music


def test_resolve_music_path_returns_path_when_file_exists(tmp_path, monkeypatch):
    (tmp_path / "inspirational.mp3").write_bytes(b"x")
    monkeypatch.setattr(music, "_MUSIC_DIR", tmp_path)
    assert music.resolve_music_path("stock_narration") == str(tmp_path / "inspirational.mp3")


def test_resolve_music_path_none_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(music, "_MUSIC_DIR", tmp_path)
    assert music.resolve_music_path("stock_narration") is None


def test_auto_music_url_uses_mood(tmp_path, monkeypatch):
    (tmp_path / "lofi-chill.mp3").write_bytes(b"x")
    monkeypatch.setattr(music, "_MUSIC_DIR", tmp_path)
    assert music.auto_music_url("dialogue_duo") == "/music/lofi-chill.mp3"


def test_resolve_auto_music_respects_global_flag(tmp_path, monkeypatch):
    (tmp_path / "inspirational.mp3").write_bytes(b"x")
    monkeypatch.setattr(music, "_MUSIC_DIR", tmp_path)
    monkeypatch.setattr(music.settings, "AUTO_MUSIC_ENABLED", False)
    assert music.resolve_auto_music("stock_narration") is None
    monkeypatch.setattr(music.settings, "AUTO_MUSIC_ENABLED", True)
    assert music.resolve_auto_music("stock_narration") == str(tmp_path / "inspirational.mp3")


@pytest.mark.asyncio
async def test_composition_returns_mood_music_url(
    client, app, db_session, verified_user, auth_headers, tmp_path, monkeypatch
):
    from app.config import settings as app_settings
    from app.db.models import Job

    job = Job(
        user_id=verified_user.id,
        topic="oceano profundo curiosidades",
        style="educational",
        duration_target=30,
        template_id="dialogue_duo",
        status="editable",
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    job_dir = app_settings.STORAGE_DIR / "jobs" / str(job.id)
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "script.json").write_text(_json.dumps({"title": "t", "scenes": [{"text": "a", "duration_hint": 5}]}))
    (job_dir / "words.json").write_text(_json.dumps([]))
    (job_dir / "narration.wav").write_bytes(b"x")

    resp = await client.get(f"/api/v1/jobs/{job.id}/composition", headers=auth_headers(verified_user))
    assert resp.status_code == 200
    body = resp.json()
    assert body["music_url"] == "/music/lofi-chill.mp3"  # mood do dialogue_duo
