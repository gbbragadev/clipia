"""Watchdog de jobs travados em processamento (heartbeat updated_at no Redis).

Contexto: time limits do Celery sao no-op no pool solo do Windows — um job real
rodou 3h39 com hard limit de 540s. O watchdog (thread no worker) e a unica
defesa contra job preso para sempre; estes testes cobrem a logica de deteccao.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.worker import tasks as worker_tasks
from tests.conftest import FakeRedis


def _iso_ago(seconds: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


@pytest.fixture()
def watchdog_env(monkeypatch):
    fake = FakeRedis()
    refund = MagicMock()
    dead_letter = MagicMock()
    monkeypatch.setattr(worker_tasks, "_redis", fake)
    monkeypatch.setattr(worker_tasks, "_refund_job_credit", refund)
    monkeypatch.setattr(worker_tasks, "_enqueue_dead_letter", dead_letter)
    return fake, refund, dead_letter


def test_reaps_processing_job_past_step_limit(watchdog_env):
    fake, refund, dead_letter = watchdog_env
    fake.hset(
        "job:stuck-1",
        mapping={"status": "processing", "current_step": "compositing", "updated_at": _iso_ago(1300)},
    )

    reaped = worker_tasks._watchdog_pass()

    assert reaped == 1
    refund.assert_called_once()
    assert refund.call_args.args[0] == "stuck-1"
    assert refund.call_args.args[1] == "failed"
    dead_letter.assert_called_once()
    # flag de cancelamento setada: a chain aborta no proximo _check_cancelled
    assert fake.get("job:stuck-1:cancelled") == "true"


def test_leaves_job_with_recent_heartbeat_alone(watchdog_env):
    fake, refund, _ = watchdog_env
    fake.hset(
        "job:alive-1",
        mapping={"status": "processing", "current_step": "compositing", "updated_at": _iso_ago(60)},
    )

    assert worker_tasks._watchdog_pass() == 0
    refund.assert_not_called()
    assert fake.get("job:alive-1:cancelled") is None


def test_respects_per_step_threshold(watchdog_env):
    fake, refund, _ = watchdog_env
    # 400s: acima do limiar de scripting (300s), abaixo do de compositing (1200s)
    fake.hset(
        "job:slow-comp",
        mapping={"status": "processing", "current_step": "compositing", "updated_at": _iso_ago(400)},
    )
    fake.hset(
        "job:slow-script",
        mapping={"status": "processing", "current_step": "scripting", "updated_at": _iso_ago(400)},
    )

    reaped = worker_tasks._watchdog_pass()

    assert reaped == 1
    assert refund.call_args.args[0] == "slow-script"
    assert fake.get("job:slow-comp:cancelled") is None


def test_seeds_heartbeat_for_legacy_job_instead_of_killing(watchdog_env):
    fake, refund, _ = watchdog_env
    fake.hset("job:legacy-1", mapping={"status": "processing", "current_step": "media"})

    assert worker_tasks._watchdog_pass() == 0
    refund.assert_not_called()
    # autocura: semeia a base de tempo para decidir na proxima passada
    assert fake.hget("job:legacy-1", "updated_at")


def test_ignores_final_statuses_and_flag_keys(watchdog_env):
    fake, refund, _ = watchdog_env
    fake.hset(
        "job:done-1",
        mapping={"status": "completed", "current_step": "", "updated_at": _iso_ago(99999)},
    )
    fake.hset(
        "job:failed-1",
        mapping={"status": "failed", "current_step": "tts", "updated_at": _iso_ago(99999)},
    )
    fake.set("job:done-1:cancelled", "true")  # key de flag nao e hash de job

    assert worker_tasks._watchdog_pass() == 0
    refund.assert_not_called()


def test_reaps_stuck_rendering_status_too(watchdog_env):
    """Re-render/export (status 'rendering') tambem e vigiado."""
    fake, refund, _ = watchdog_env
    fake.hset(
        "job:render-1",
        mapping={"status": "rendering", "current_step": "encoding", "updated_at": _iso_ago(2000)},
    )

    assert worker_tasks._watchdog_pass() == 1
    assert refund.call_args.args[0] == "render-1"


def test_update_job_writes_heartbeat(watchdog_env):
    fake, _, _ = watchdog_env
    worker_tasks._update_job("hb-1", "processing", "tts", 0.3, detail="x")

    stamp = fake.hget("job:hb-1", "updated_at")
    assert stamp
    parsed = datetime.fromisoformat(stamp)
    assert (datetime.now(timezone.utc) - parsed).total_seconds() < 5
