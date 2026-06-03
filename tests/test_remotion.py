import json

from app.config import settings
from app.services.remotion import build_composition_props


def _make_job(tmp_path, job_id):
    job_dir = tmp_path / "jobs" / job_id
    (job_dir / "media").mkdir(parents=True)
    return job_dir


def test_build_props_resolves_assets_and_merges_editor_state(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_DIR", tmp_path)
    job_dir = _make_job(tmp_path, "job1")
    (job_dir / "script.json").write_text(
        json.dumps({"title": "T", "scenes": [{"text": "a", "keywords_en": [], "duration_hint": 5}]}),
        encoding="utf-8",
    )
    (job_dir / "words.json").write_text(json.dumps([{"word": "a", "start": 0, "end": 1}]), encoding="utf-8")
    (job_dir / "media" / "scene_0.mp4").write_bytes(b"x")
    (job_dir / "editor_state.json").write_text(
        json.dumps(
            {
                "composition": {
                    "overlays": [{"type": "questionBox", "startFrame": 0, "endFrame": 30, "config": {}}],
                    "subtitleStyle": {"preset": "tiktok"},
                    "musicVolume": 0.3,
                }
            }
        ),
        encoding="utf-8",
    )

    props = build_composition_props("job1", backend_url="http://x:8005")

    assert props["isRendering"] is True
    assert props["audioUrl"] == "http://x:8005/storage/jobs/job1/narration.wav"
    assert props["mediaUrls"] == ["http://x:8005/storage/jobs/job1/media/scene_0.mp4"]
    # editor edits win over defaults
    assert props["overlays"][0]["type"] == "questionBox"
    assert props["subtitleStyle"]["preset"] == "tiktok"
    assert props["musicVolume"] == 0.3
    # watermark present when enabled (default)
    assert props.get("watermark") == settings.WATERMARK_TEXT


def test_build_props_reads_legacy_cp1252(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_DIR", tmp_path)
    job_dir = _make_job(tmp_path, "job2")
    # Legacy worker wrote cp1252 (accented title)
    (job_dir / "script.json").write_bytes(
        json.dumps({"title": "Oceano É", "scenes": []}, ensure_ascii=False).encode("cp1252")
    )
    (job_dir / "words.json").write_text(json.dumps([]), encoding="utf-8")

    props = build_composition_props("job2", backend_url="http://x:8005")

    assert props["title"] == "Oceano É"


def test_build_props_without_editor_state_uses_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_DIR", tmp_path)
    job_dir = _make_job(tmp_path, "job3")
    (job_dir / "script.json").write_text(json.dumps({"title": "T", "scenes": []}), encoding="utf-8")
    (job_dir / "words.json").write_text(json.dumps([]), encoding="utf-8")

    props = build_composition_props("job3", backend_url="http://x:8005")

    assert props["overlays"] == []
    assert props["subtitleStyle"]["preset"] == "minimal"
