"""Telemetria de economia: duração por etapa + custo estimado de API por job."""

from datetime import datetime, timedelta, timezone

import pytest

from app.worker import tasks as worker_tasks
from tests.conftest import FakeRedis


@pytest.fixture()
def redis_env(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(worker_tasks, "_redis", fake)
    return fake


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def test_update_job_records_first_step_timestamp_once(redis_env):
    worker_tasks._update_job("t1", "processing", "scripting", 0.1)
    first = redis_env.hget("job:t1", "t:scripting")
    assert first

    worker_tasks._update_job("t1", "processing", "scripting", 0.16)
    assert redis_env.hget("job:t1", "t:scripting") == first  # só o INÍCIO da etapa


def test_build_telemetry_computes_step_durations(redis_env):
    base = datetime.now(timezone.utc) - timedelta(seconds=100)
    redis_env.hset(
        "job:t2",
        mapping={
            "created_at": _iso(base),
            "template_id": "stock_narration",
            "voice_provider": "edge",
            "t:scripting": _iso(base),
            "t:tts": _iso(base + timedelta(seconds=30)),
            "t:compositing": _iso(base + timedelta(seconds=50)),
        },
    )

    tel = worker_tasks._build_telemetry("t2", {"narration": "abc", "scenes": [{"text": "abc"}]})

    assert tel["steps"]["scripting"] == pytest.approx(30, abs=2)
    assert tel["steps"]["tts"] == pytest.approx(20, abs=2)
    assert tel["total_seconds"] == pytest.approx(100, abs=5)
    assert tel["api_cost_usd_est"] > 0


def test_cost_estimate_scales_with_template_and_voice(redis_env):
    narration = "x" * 1000  # 1k chars
    script = {"narration": narration, "scenes": [{"text": "a"}] * 6}

    redis_env.hset("job:cheap", mapping={"template_id": "stock_narration", "voice_provider": "edge"})
    cheap = worker_tasks._estimate_api_cost_usd("cheap", script)

    redis_env.hset("job:eleven", mapping={"template_id": "stock_narration", "voice_provider": "elevenlabs"})
    eleven = worker_tasks._estimate_api_cost_usd("eleven", script)

    redis_env.hset("job:img", mapping={"template_id": "novelinha_historica", "voice_provider": "elevenlabs"})
    img = worker_tasks._estimate_api_cost_usd("img", script)

    assert cheap < eleven < img  # edge < +elevenlabs < +6 imagens IA
    # elevenlabs: 1k chars ≈ constante configurada
    from app.config import settings

    assert eleven - cheap == pytest.approx(settings.API_COST_ELEVENLABS_PER_1K_CHARS_USD, abs=0.001)


def test_cost_estimate_custom_script_skips_llm_call(redis_env):
    script = {"narration": "abc", "scenes": [{"text": "abc"}]}
    redis_env.hset("job:auto", mapping={"template_id": "stock_narration", "voice_provider": "edge"})
    redis_env.hset(
        "job:custom",
        mapping={"template_id": "stock_narration", "voice_provider": "edge", "custom_script": "1"},
    )

    from app.config import settings

    diff = worker_tasks._estimate_api_cost_usd("auto", script) - worker_tasks._estimate_api_cost_usd("custom", script)
    assert diff == pytest.approx(settings.API_COST_LLM_PER_CALL_USD, abs=0.0001)
