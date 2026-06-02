from __future__ import annotations

import asyncio
import importlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.db.models import Job, User
from app.worker import tasks as worker_tasks
from tests.voice_test_support import create_job, create_test_env


class FakeTaskSelf:
    def __init__(self, retries: int = 0):
        self.request = SimpleNamespace(retries=retries)

    def retry(self, **kwargs):
        raise RuntimeError(f"retry:{kwargs['countdown']}")


class LocalRedis:
    def __init__(self):
        self.hashes: dict[str, dict[str, str]] = {}
        self.values: dict[str, str] = {}

    def hset(self, key: str, mapping=None, **kwargs):
        if mapping is None:
            mapping = {}
        mapping.update({k: str(v) for k, v in kwargs.items()})
        self.hashes.setdefault(key, {}).update({k: str(v) for k, v in mapping.items()})

    def hgetall(self, key: str):
        return dict(self.hashes.get(key, {}))

    def hget(self, key: str, field: str):
        return self.hashes.get(key, {}).get(field)

    def set(self, key: str, value: str):
        self.values[key] = str(value)

    def get(self, key: str):
        return self.values.get(key)


def test_synthesize_audio_edge_default(monkeypatch, tmp_path):
    redis_client = LocalRedis()
    output_path = tmp_path / "narration.wav"
    monkeypatch.setattr(worker_tasks, "_redis", redis_client)
    monkeypatch.setattr(worker_tasks, "_check_cancelled", lambda _job_id: False)
    monkeypatch.setattr(worker_tasks, "get_job_dir", lambda _job_id: tmp_path)
    monkeypatch.setattr(worker_tasks, "synthesize_narration", lambda **_kwargs: output_path.write_bytes(b"x" * 12000))

    result = worker_tasks.task_synthesize_audio.run.__func__(
        FakeTaskSelf(),
        {"narration": "texto", "_duration_target": 45},
        "job-edge-default",
        "stock_narration",
    )

    assert result == str(output_path)


def test_synthesize_audio_edge_explicit(monkeypatch, tmp_path):
    redis_client = LocalRedis()
    redis_client.hset("job:job-edge", mapping={"voice_provider": "edge"})
    output_path = tmp_path / "narration.wav"
    monkeypatch.setattr(worker_tasks, "_redis", redis_client)
    monkeypatch.setattr(worker_tasks, "_check_cancelled", lambda _job_id: False)
    monkeypatch.setattr(worker_tasks, "get_job_dir", lambda _job_id: tmp_path)
    synth_calls = []
    monkeypatch.setattr(
        worker_tasks,
        "synthesize_narration",
        lambda **kwargs: (synth_calls.append(kwargs), output_path.write_bytes(b"x" * 12000)),
    )

    worker_tasks.task_synthesize_audio.run.__func__(
        FakeTaskSelf(),
        {"narration": "texto", "_duration_target": 45},
        "job-edge",
        "stock_narration",
    )

    assert synth_calls[0]["voice_id"] == "pt-BR-AntonioNeural"


def test_synthesize_audio_edge_ignores_non_edge_template_voice(monkeypatch, tmp_path):
    redis_client = LocalRedis()
    redis_client.hset("job:job-edge-ai-template", mapping={"voice_provider": "edge"})
    output_path = tmp_path / "narration.wav"
    synth_calls = []
    monkeypatch.setattr(worker_tasks, "_redis", redis_client)
    monkeypatch.setattr(worker_tasks, "_check_cancelled", lambda _job_id: False)
    monkeypatch.setattr(worker_tasks, "get_job_dir", lambda _job_id: tmp_path)
    monkeypatch.setattr(
        worker_tasks,
        "synthesize_narration",
        lambda **kwargs: (synth_calls.append(kwargs), output_path.write_bytes(b"x" * 12000)),
    )

    worker_tasks.task_synthesize_audio.run.__func__(
        FakeTaskSelf(),
        {"narration": "texto", "_duration_target": 45},
        "job-edge-ai-template",
        "novelinha_historica",
    )

    assert synth_calls[0]["voice_id"] == "pt-BR-AntonioNeural"


def test_synthesize_audio_elevenlabs(monkeypatch, tmp_path):
    redis_client = LocalRedis()
    redis_client.hset(
        "job:job-elevenlabs",
        mapping={
            "voice_provider": "elevenlabs",
            "voice_config": json.dumps({"voice_id": "el_abc123"}),
        },
    )
    output_path = tmp_path / "narration.wav"
    synth_mock = AsyncMock(side_effect=lambda **_kwargs: output_path.write_bytes(b"x" * 12000) or output_path)
    monkeypatch.setattr(worker_tasks, "_redis", redis_client)
    monkeypatch.setattr(worker_tasks, "_check_cancelled", lambda _job_id: False)
    monkeypatch.setattr(worker_tasks, "get_job_dir", lambda _job_id: tmp_path)
    monkeypatch.setattr("app.services.elevenlabs_provider.ElevenLabsProvider.synthesize", synth_mock)

    result = worker_tasks.task_synthesize_audio.run.__func__(
        FakeTaskSelf(),
        {"narration": "texto", "_duration_target": 45},
        "job-elevenlabs",
        "stock_narration",
    )

    assert result == str(output_path)
    synth_mock.assert_awaited_once()


def test_synthesize_audio_elevenlabs_uses_template_default_voice(monkeypatch, tmp_path):
    redis_client = LocalRedis()
    redis_client.hset("job:job-elevenlabs-template", mapping={"voice_provider": "elevenlabs"})
    output_path = tmp_path / "narration.wav"
    synth_mock = AsyncMock(side_effect=lambda **_kwargs: output_path.write_bytes(b"x" * 12000) or output_path)
    monkeypatch.setattr(worker_tasks, "_redis", redis_client)
    monkeypatch.setattr(worker_tasks, "_check_cancelled", lambda _job_id: False)
    monkeypatch.setattr(worker_tasks, "get_job_dir", lambda _job_id: tmp_path)
    monkeypatch.setattr("app.services.elevenlabs_provider.ElevenLabsProvider.synthesize", synth_mock)

    result = worker_tasks.task_synthesize_audio.run.__func__(
        FakeTaskSelf(),
        {"narration": "texto", "_duration_target": 45},
        "job-elevenlabs-template",
        "novelinha_historica",
    )

    assert result == str(output_path)
    synth_mock.assert_awaited_once()
    assert synth_mock.await_args.kwargs["voice_id"] == "KHmfNHtEjHhLK9eER20w"


def test_synthesize_audio_custom(monkeypatch, tmp_path):
    redis_client = LocalRedis()
    source_path = tmp_path / "source.wav"
    source_path.write_bytes(b"audio")
    output_path = tmp_path / "narration.wav"
    redis_client.hset(
        "job:job-custom",
        mapping={
            "voice_provider": "custom",
            "voice_config": json.dumps({"source_path": str(source_path)}),
        },
    )
    normalize_calls = []
    monkeypatch.setattr(worker_tasks, "_redis", redis_client)
    monkeypatch.setattr(worker_tasks, "_check_cancelled", lambda _job_id: False)
    monkeypatch.setattr(worker_tasks, "get_job_dir", lambda _job_id: tmp_path)
    monkeypatch.setattr(
        "app.services.custom_audio_provider.normalize_audio",
        lambda src, dst: (normalize_calls.append((src, dst)), output_path.write_bytes(b"x" * 12000)),
    )

    result = worker_tasks.task_synthesize_audio.run.__func__(
        FakeTaskSelf(),
        {"narration": "texto", "_duration_target": 45},
        "job-custom",
        "stock_narration",
    )

    assert result == str(output_path)
    assert normalize_calls == [(str(source_path), str(output_path))]


def test_synthesize_audio_custom_missing_source(monkeypatch, tmp_path):
    redis_client = LocalRedis()
    redis_client.hset(
        "job:job-custom-missing",
        mapping={
            "voice_provider": "custom",
            "voice_config": json.dumps({}),
        },
    )
    failures = []
    monkeypatch.setattr(worker_tasks, "_redis", redis_client)
    monkeypatch.setattr(worker_tasks, "_check_cancelled", lambda _job_id: False)
    monkeypatch.setattr(worker_tasks, "get_job_dir", lambda _job_id: tmp_path)
    monkeypatch.setattr(worker_tasks, "_fail_job", lambda job_id, error: failures.append((job_id, error)))

    with pytest.raises(RuntimeError, match="Custom audio source not found"):
        worker_tasks.task_synthesize_audio.run.__func__(
            FakeTaskSelf(retries=2),
            {"narration": "texto", "_duration_target": 45},
            "job-custom-missing",
            "stock_narration",
        )

    assert failures == [("job-custom-missing", "TTS failed: Custom audio source not found")]


def test_synthesize_audio_elevenlabs_no_voice_id(monkeypatch, tmp_path):
    redis_client = LocalRedis()
    redis_client.hset(
        "job:job-el-missing",
        mapping={
            "voice_provider": "elevenlabs",
            "voice_config": json.dumps({}),
        },
    )
    failures = []
    monkeypatch.setattr(worker_tasks, "_redis", redis_client)
    monkeypatch.setattr(worker_tasks, "_check_cancelled", lambda _job_id: False)
    monkeypatch.setattr(worker_tasks, "get_job_dir", lambda _job_id: tmp_path)
    monkeypatch.setattr(worker_tasks, "_fail_job", lambda job_id, error: failures.append((job_id, error)))

    with pytest.raises(RuntimeError, match="No ElevenLabs voice_id specified"):
        worker_tasks.task_synthesize_audio.run.__func__(
            FakeTaskSelf(retries=2),
            {"narration": "texto", "_duration_target": 45},
            "job-el-missing",
            "stock_narration",
        )

    assert failures == [("job-el-missing", "TTS failed: No ElevenLabs voice_id specified")]


def test_refund_uses_credit_cost(monkeypatch, tmp_path):
    db_engine = importlib.import_module("app.db.engine")
    env = create_test_env(tmp_path, monkeypatch)
    job = create_job(env, status="processing", credit_cost=2)

    async def _before():
        async with env.session_factory() as session:
            return (await session.get(User, env.verified_user.id)).credits

    monkeypatch.setattr(db_engine, "async_session", env.session_factory)
    before = asyncio.run(_before())
    worker_tasks._refund_job_credit(str(job.id), "failed", "boom")

    async def _after():
        async with env.session_factory() as session:
            refreshed_user = await session.get(User, env.verified_user.id)
            refreshed_job = await session.get(Job, job.id)
            return refreshed_user.credits, refreshed_job.status

    credits, status = asyncio.run(_after())
    assert credits == before + 2
    assert status == "failed"


def test_dispatch_pipeline_stores_voice_config(monkeypatch):
    redis_client = LocalRedis()
    apply_async_calls = []

    class FakeSig:
        def __or__(self, _other):
            return self

    class FakeChain:
        def __call__(self, *_args, **_kwargs):
            return SimpleNamespace(apply_async=lambda: apply_async_calls.append(True))

    monkeypatch.setattr(worker_tasks, "_redis", redis_client)
    monkeypatch.setattr("celery.chain", FakeChain())

    worker_tasks.dispatch_pipeline(
        "job-dispatch",
        "Tema",
        "educational",
        45,
        voice_provider="elevenlabs",
        voice_config={"voice_id": "el_abc123"},
    )

    payload = redis_client.hgetall("job:job-dispatch")
    assert payload["voice_provider"] == "elevenlabs"
    assert json.loads(payload["voice_config"]) == {"voice_id": "el_abc123"}
    assert apply_async_calls == [True]


def test_dispatch_pipeline_backwards_compatible(monkeypatch):
    redis_client = LocalRedis()

    class FakeChain:
        def __call__(self, *_args, **_kwargs):
            return SimpleNamespace(apply_async=lambda: None)

    monkeypatch.setattr(worker_tasks, "_redis", redis_client)
    monkeypatch.setattr("celery.chain", FakeChain())

    worker_tasks.dispatch_pipeline("job-legacy", "Tema", "educational", 45)

    payload = redis_client.hgetall("job:job-legacy")
    assert payload["voice_provider"] == "edge"
