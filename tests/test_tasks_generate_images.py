from unittest.mock import MagicMock

import pytest


def test_skip_when_template_is_not_ai_image(monkeypatch, tmp_path):
    from app.worker.tasks import task_generate_images

    monkeypatch.setattr("app.worker.tasks.get_job_dir", lambda jid: tmp_path)

    data_in = {"script": {"scenes": [{"text": "x", "duration_hint": 5}]}}

    result = task_generate_images.run(data_in, "job-1", "stock_narration")

    assert result == data_in
    assert "image_paths" not in result


def test_generates_images_and_populates_image_paths(monkeypatch, tmp_path):
    from app.worker.tasks import task_generate_images

    job_dir = tmp_path / "job-42"
    job_dir.mkdir()
    script = {"scenes": [{"text": f"cena {i}", "visual_hint": f"hint {i}", "duration_hint": 5} for i in range(1, 7)]}
    (job_dir / "script.json").write_text(
        '{"scenes": [{"text":"x","visual_hint":"h","duration_hint":5}]}',
        encoding="utf-8",
    )

    monkeypatch.setattr("app.worker.tasks.get_job_dir", lambda jid: job_dir)

    fake_provider = MagicMock()

    def fake_generate(prompt: str, output_path):
        output_path.write_bytes(b"\x89PNG\r\n\x1a\nfake")
        return output_path

    fake_provider.generate = MagicMock(side_effect=fake_generate)
    monkeypatch.setattr(
        "app.worker.tasks.OpenAIImageProvider",
        lambda **kw: fake_provider,
    )
    monkeypatch.setattr("app.worker.tasks._check_cancelled", lambda jid: False)
    monkeypatch.setattr("app.worker.tasks._update_job", lambda *a, **kw: None)

    data_in = {"script": script}
    result = task_generate_images.run(data_in, "job-42", "novelinha_historica")

    assert "image_paths" in result
    assert len(result["image_paths"]) == 6
    assert fake_provider.generate.call_count == 6
    from pathlib import Path

    expected_parent = (job_dir / "images").resolve()
    for path_str in result["image_paths"]:
        assert expected_parent in Path(path_str).resolve().parents


def test_fetch_media_reuses_image_paths_when_ai_image(monkeypatch, tmp_path):
    from app.worker.tasks import task_fetch_media

    monkeypatch.setattr("app.worker.tasks._check_cancelled", lambda jid: False)
    monkeypatch.setattr("app.worker.tasks._update_job", lambda *a, **kw: None)

    image_paths = [str(tmp_path / f"scene_{i}.png") for i in range(1, 7)]
    from pathlib import Path

    for p in image_paths:
        Path(p).write_bytes(b"\x89PNG")

    data_in = {
        "script": {"scenes": [{"text": f"x{i}"} for i in range(6)]},
        "image_paths": image_paths,
    }

    result = task_fetch_media.run(data_in, "job-am", "novelinha_historica")

    assert result.get("media_paths") == image_paths


def test_fetch_media_scans_images_dir_when_image_paths_missing(monkeypatch, tmp_path):
    """Integration gap: task_transcribe_audio returns a fresh dict that drops
    image_paths. fetch_media must recover by scanning the job's images dir."""
    from app.worker.tasks import task_fetch_media

    monkeypatch.setattr("app.worker.tasks._check_cancelled", lambda jid: False)
    monkeypatch.setattr("app.worker.tasks._update_job", lambda *a, **kw: None)

    job_dir = tmp_path / "job-scan"
    job_dir.mkdir()
    img_dir = job_dir / "images"
    img_dir.mkdir()
    for i in range(1, 7):
        (img_dir / f"scene_{i}.png").write_bytes(b"\x89PNG")

    monkeypatch.setattr("app.worker.tasks.get_job_dir", lambda jid: job_dir)

    # image_paths NOT in data_in — simulating post-transcribe state
    data_in = {"script": {"scenes": [{"text": f"x{i}"} for i in range(6)]}}

    result = task_fetch_media.run(data_in, "job-scan", "novelinha_historica")

    assert len(result.get("media_paths", [])) == 6
    assert all("scene_" in p and p.endswith(".png") for p in result["media_paths"])


def test_fails_job_on_moderation_block(monkeypatch, tmp_path):
    from app.services.image_provider import ModerationBlockedError
    from app.worker.tasks import task_generate_images

    job_dir = tmp_path / "job-mb"
    job_dir.mkdir()
    monkeypatch.setattr("app.worker.tasks.get_job_dir", lambda jid: job_dir)

    fake_provider = MagicMock()
    fake_provider.generate.side_effect = ModerationBlockedError("bloqueada")
    monkeypatch.setattr("app.worker.tasks.OpenAIImageProvider", lambda **kw: fake_provider)
    monkeypatch.setattr("app.worker.tasks._check_cancelled", lambda jid: False)
    monkeypatch.setattr("app.worker.tasks._update_job", lambda *a, **kw: None)

    failed = {"called": False}

    def fake_fail(jid, err):
        failed["called"] = True
        failed["err"] = err

    monkeypatch.setattr("app.worker.tasks._fail_job", fake_fail)

    script = {"scenes": [{"text": "x", "visual_hint": "y", "duration_hint": 5}]}
    with pytest.raises(ModerationBlockedError):
        task_generate_images.run({"script": script}, "job-mb", "novelinha_historica")

    assert failed["called"] is True
    assert "moderação" in failed["err"].lower() or "moderacao" in failed["err"].lower()
