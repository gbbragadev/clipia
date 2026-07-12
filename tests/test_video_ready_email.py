"""Notificação "seu vídeo está pronto" no finalize: 1x por job, best-effort.

Jobs levam 3-10 min; sem chamada de volta, quem fecha a aba não retorna. O envio
é idempotente (SET NX no Redis) para re-render/retry do finalize não repetir o
email, e nunca pode falhar o finalize (best-effort).
"""

from app.worker import tasks as worker_tasks


def _arm(monkeypatch, sent: list, recipient=("gui@teste.com", "Gui", "curiosidades do oceano")):
    monkeypatch.setattr(worker_tasks, "_video_ready_recipient", lambda _job_id: recipient)
    monkeypatch.setattr(
        worker_tasks,
        "send_video_ready_email",
        lambda email, name, topic, job_id: sent.append((email, job_id)) or True,
    )


def test_video_ready_email_sent_once(monkeypatch):
    sent: list = []
    _arm(monkeypatch, sent)

    worker_tasks._send_video_ready_email("job-noti")
    worker_tasks._send_video_ready_email("job-noti")  # retry/re-render do finalize

    assert sent == [("gui@teste.com", "job-noti")], "SET NX garante 1 email por job"


def test_video_ready_email_never_raises(monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("smtp fora do ar")

    monkeypatch.setattr(worker_tasks, "_video_ready_recipient", lambda _job_id: ("a@b.c", "X", "t"))
    monkeypatch.setattr(worker_tasks, "send_video_ready_email", boom)

    worker_tasks._send_video_ready_email("job-boom")  # não pode propagar


def test_video_ready_email_skips_unknown_job(monkeypatch):
    sent: list = []
    _arm(monkeypatch, sent, recipient=None)

    worker_tasks._send_video_ready_email("job-fantasma")

    assert sent == []
