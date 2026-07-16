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
    assert props["audioUrl"].split("?")[0] == "http://x:8005/storage/jobs/job1/narration.wav"
    assert "sig=" in props["audioUrl"]  # midia privada vem assinada (HMAC)
    assert [u.split("?")[0] for u in props["mediaUrls"]] == ["http://x:8005/storage/jobs/job1/media/scene_0.mp4"]
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


def test_build_props_falls_back_to_ai_images(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_DIR", tmp_path)
    job_dir = tmp_path / "jobs" / "job4"
    (job_dir / "images").mkdir(parents=True)
    (job_dir / "media").mkdir()
    (job_dir / "script.json").write_text(
        json.dumps({"title": "T", "scenes": [{"text": "a", "duration_hint": 5}, {"text": "b", "duration_hint": 5}]}),
        encoding="utf-8",
    )
    (job_dir / "words.json").write_text(json.dumps([]), encoding="utf-8")
    # imagens 1-based como o worker grava (tasks.py: scene_{i+1}.png)
    (job_dir / "images" / "scene_1.png").write_bytes(b"x")
    (job_dir / "images" / "scene_2.png").write_bytes(b"x")

    props = build_composition_props("job4", backend_url="http://x:8005")

    assert [u.split("?")[0] for u in props["mediaUrls"]] == [
        "http://x:8005/storage/jobs/job4/images/scene_1.png",
        "http://x:8005/storage/jobs/job4/images/scene_2.png",
    ]


def test_build_props_applies_scene_order_only_to_authoritative_media(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_DIR", tmp_path)
    job_dir = _make_job(tmp_path, "job5")
    scenes = [
        {"text": "c", "duration_hint": 5},
        {"text": "a", "duration_hint": 5},
        {"text": "b", "duration_hint": 5},
    ]
    (job_dir / "script.json").write_text(json.dumps({"title": "T", "scenes": scenes}), encoding="utf-8")
    (job_dir / "words.json").write_text("[]", encoding="utf-8")
    for index in range(3):
        (job_dir / "media" / f"scene_{index}.mp4").write_bytes(b"owned")
    (job_dir / "editor_state.json").write_text(
        json.dumps(
            {
                "composition": {
                    "sceneOrder": [2, 0, 1],
                    "mediaUrls": [
                        "file:///etc/passwd",
                        "http://169.254.169.254/latest/meta-data",
                        r"\\server\share\clip.mp4",
                    ],
                }
            }
        ),
        encoding="utf-8",
    )

    props = build_composition_props("job5", backend_url="http://x:8005")

    assert [url.split("?")[0] for url in props["mediaUrls"]] == [
        "http://x:8005/storage/jobs/job5/media/scene_2.mp4",
        "http://x:8005/storage/jobs/job5/media/scene_0.mp4",
        "http://x:8005/storage/jobs/job5/media/scene_1.mp4",
    ]
    assert [scene["text"] for scene in props["scenes"]] == ["c", "a", "b"]
