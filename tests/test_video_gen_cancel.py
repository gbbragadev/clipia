"""Cancelamento durante a geração de vídeo IA (Seedance).

Antes: o cancel só era checado ao ENTRAR na task; os polls de 6-10min seguiam,
o job completava e COBRAVA os 30 créditos de um vídeo que o usuário cancelou.
Agora o provider recebe um callable `cancelled` e para antes de submeter cada
cena e entre polls; a task trata como cancelamento (refund idempotente), não erro.
"""

from types import SimpleNamespace

import pytest

from app.services import video_gen_provider as vgp
from app.worker import tasks as worker_tasks


class FakeTaskSelf:
    def __init__(self, retries: int = 0):
        self.request = SimpleNamespace(retries=retries)


@pytest.mark.asyncio
async def test_generate_scenes_cancelled_before_submit(tmp_path):
    """Flag de cancelamento ligada → nenhuma cena é submetida (sem rede, sem custo)."""
    with pytest.raises(vgp.VideoGenCancelled):
        await vgp.generate_scenes(["um prompt de teste"], str(tmp_path), cancelled=lambda: True)


def test_task_generate_videos_treats_cancel_as_cancel_not_error(monkeypatch, tmp_path):
    """VideoGenCancelled no provider → _cancel_job (estado cancelled + refund
    idempotente) e early-return, sem marcar o job como erro."""
    cancelled_jobs: list[str] = []
    failed_jobs: list[str] = []

    async def fake_generate_scenes(prompts, out_dir, duration=None, cancelled=None):
        raise vgp.VideoGenCancelled("cancelado pelo usuario")

    monkeypatch.setattr(vgp, "generate_scenes", fake_generate_scenes)
    monkeypatch.setattr(worker_tasks, "_cancel_job", lambda job_id, detail="": cancelled_jobs.append(job_id))
    monkeypatch.setattr(worker_tasks, "_fail_job", lambda job_id, error: failed_jobs.append(job_id))
    monkeypatch.setattr(worker_tasks, "get_job_dir", lambda _job_id: tmp_path)

    data = {"script": {"scenes": [{"text": "a", "visual_hint": "v", "duration_hint": 5}]}}
    result = worker_tasks.task_generate_videos.run.__func__(FakeTaskSelf(), data, "job-cancel", "ai_video")

    assert result == data
    assert cancelled_jobs == ["job-cancel"]
    assert failed_jobs == []
