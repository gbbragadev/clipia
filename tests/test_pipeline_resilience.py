from pathlib import Path
from types import SimpleNamespace

import pytest
from celery.exceptions import SoftTimeLimitExceeded

from app.worker import tasks as worker_tasks


class RetryTriggered(Exception):
    pass


class FakeTaskSelf:
    def __init__(self, retries: int = 0):
        self.request = SimpleNamespace(retries=retries)
        self.retry_calls: list[dict] = []

    def retry(self, **kwargs):
        self.retry_calls.append(kwargs)
        raise RetryTriggered()


@pytest.mark.asyncio
async def test_generate_script_retries_then_succeeds(monkeypatch, tmp_path):
    calls = {"count": 0}

    def flaky_generate(*_args, **_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("temporary upstream failure")
        return {"title": "ok", "narration": "texto", "scenes": [{"duration_hint": 7}]}

    monkeypatch.setattr(worker_tasks, "generate_script", flaky_generate)
    monkeypatch.setattr(worker_tasks, "get_job_dir", lambda _job_id: tmp_path)

    first_attempt = FakeTaskSelf(retries=0)
    with pytest.raises(RetryTriggered):
        worker_tasks.task_generate_script.run.__func__(first_attempt, "job-1", "Tema", "educational", 45, "stock_narration")

    assert first_attempt.retry_calls[0]["countdown"] == 10

    second_attempt = FakeTaskSelf(retries=1)
    result = worker_tasks.task_generate_script.run.__func__(second_attempt, "job-1", "Tema", "educational", 45, "stock_narration")

    assert result["title"] == "ok"
    assert result["_duration_target"] == 45


@pytest.mark.asyncio
async def test_generate_script_stops_retrying_and_fails_after_limit(monkeypatch, tmp_path):
    failures: list[str] = []

    monkeypatch.setattr(worker_tasks, "generate_script", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("rate limited")))
    monkeypatch.setattr(worker_tasks, "get_job_dir", lambda _job_id: tmp_path)
    monkeypatch.setattr(worker_tasks, "_fail_job", lambda job_id, error: failures.append(f"{job_id}:{error}"))

    exhausted = FakeTaskSelf(retries=2)
    with pytest.raises(RuntimeError, match="rate limited"):
        worker_tasks.task_generate_script.run.__func__(exhausted, "job-2", "Tema", "educational", 45, "stock_narration")

    assert failures == ["job-2:Script generation failed: rate limited"]


@pytest.mark.asyncio
async def test_soft_time_limit_triggers_timeout_handler(monkeypatch):
    calls: list[tuple[str, str]] = []

    monkeypatch.setattr(worker_tasks, "transcribe_with_timestamps", lambda _path: (_ for _ in ()).throw(SoftTimeLimitExceeded()))
    monkeypatch.setattr(worker_tasks, "_handle_soft_timeout", lambda job_id, task_name: calls.append((job_id, task_name)))
    monkeypatch.setattr(worker_tasks, "get_job_dir", lambda _job_id: Path("/tmp"))

    with pytest.raises(SoftTimeLimitExceeded):
        worker_tasks.task_transcribe_audio.run.__func__(FakeTaskSelf(), "/tmp/audio.wav", "job-3")

    assert calls == [("job-3", "transcribe_audio")]


@pytest.mark.asyncio
async def test_job_cancellation_endpoint_and_task_short_circuit(client, verified_user, auth_headers, job_factory, app, monkeypatch):
    job = await job_factory(status="processing")
    cancelled: list[str] = []

    response = await client.post(f"/api/v1/jobs/{job.id}/cancel", headers=auth_headers(verified_user))
    monkeypatch.setattr(worker_tasks, "_cancel_job", lambda job_id, detail="": cancelled.append(job_id))

    task_result = worker_tasks.task_fetch_media.run.__func__(
        FakeTaskSelf(),
        {"script": {"scenes": []}},
        str(job.id),
        "stock_narration",
    )

    assert response.status_code == 200
    assert response.json()["status"] == "cancelling"
    assert app.state.fake_redis.get(f"job:{job.id}:cancelled") == "true"
    assert task_result == {"cancelled": True}
    assert cancelled == [str(job.id)]


@pytest.mark.asyncio
async def test_progress_detail_is_written_to_redis(monkeypatch, tmp_path):
    class LocalRedis:
        def __init__(self):
            self.hashes = {}
            self.values = {}

        def hset(self, key, mapping):
            self.hashes.setdefault(key, {}).update({k: str(v) for k, v in mapping.items()})

        def hgetall(self, key):
            return dict(self.hashes.get(key, {}))

        def get(self, key):
            return self.values.get(key)

        def set(self, key, value):
            self.values[key] = str(value)

    redis_stub = LocalRedis()
    monkeypatch.setattr(worker_tasks, "_redis", redis_stub)
    monkeypatch.setattr(worker_tasks, "transcribe_with_timestamps", lambda _path: [{"word": "ola", "start": 0, "end": 0.5}])

    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "script.json").write_text('{"scenes":[{"duration_hint":7}],"narration":"texto"}')
    monkeypatch.setattr(worker_tasks, "get_job_dir", lambda _job_id: tmp_path)

    result = worker_tasks.task_transcribe_audio.run.__func__(FakeTaskSelf(), "/tmp/audio.wav", "job-4")

    assert result["words"][0]["word"] == "ola"
    payload = redis_stub.hgetall("job:job-4")
    assert payload["detail"] == "Transcricao concluida."
