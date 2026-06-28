import json

from app.services import remotion


def _make_job(tmp_path, with_state=None):
    job_dir = tmp_path / "jobs" / "job1"
    (job_dir / "media").mkdir(parents=True)
    (job_dir / "script.json").write_text(json.dumps({"title": "t", "scenes": [{"text": "a", "duration_hint": 5}]}))
    (job_dir / "words.json").write_text(json.dumps([]))
    if with_state is not None:
        (job_dir / "editor_state.json").write_text(json.dumps({"composition": with_state}))
    return job_dir


def test_audio_filename_overrides_audio_url(tmp_path, monkeypatch):
    _make_job(tmp_path)
    monkeypatch.setattr(remotion.settings, "STORAGE_DIR", tmp_path)
    props = remotion.build_composition_props("job1", audio_filename="narration_sfx.wav")
    assert props["audioUrl"].endswith("/storage/jobs/job1/narration_sfx.wav")


def test_default_music_url_applied_when_no_editor_state(tmp_path, monkeypatch):
    _make_job(tmp_path)
    monkeypatch.setattr(remotion.settings, "STORAGE_DIR", tmp_path)
    props = remotion.build_composition_props("job1", default_music_url="/music/lofi-chill.mp3")
    assert props["musicUrl"] == "/music/lofi-chill.mp3"


def test_editor_state_null_music_is_respected(tmp_path, monkeypatch):
    _make_job(tmp_path, with_state={"musicUrl": None})
    monkeypatch.setattr(remotion.settings, "STORAGE_DIR", tmp_path)
    props = remotion.build_composition_props("job1", default_music_url="/music/lofi-chill.mp3")
    assert props["musicUrl"] is None  # usuario removeu a musica no editor -> respeitar


def test_editor_state_track_overrides_default(tmp_path, monkeypatch):
    _make_job(tmp_path, with_state={"musicUrl": "/music/happy-pop.mp3"})
    monkeypatch.setattr(remotion.settings, "STORAGE_DIR", tmp_path)
    props = remotion.build_composition_props("job1", default_music_url="/music/lofi-chill.mp3")
    assert props["musicUrl"] == "/music/happy-pop.mp3"
