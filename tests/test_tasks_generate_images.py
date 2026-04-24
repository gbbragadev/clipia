def test_skip_when_template_is_not_ai_image(monkeypatch, tmp_path):
    from app.worker.tasks import task_generate_images

    monkeypatch.setattr("app.worker.tasks.get_job_dir", lambda jid: tmp_path)

    data_in = {"script": {"scenes": [{"text": "x", "duration_hint": 5}]}}

    result = task_generate_images.run(data_in, "job-1", "stock_narration")

    assert result == data_in
    assert "image_paths" not in result
