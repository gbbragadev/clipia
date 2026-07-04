from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from app.api import routes as api_routes
from app.db.models import User
from app.models import GenerateRequest, RegenerateTTSRequest
from app.services.tts import synthesize_narration
from tests.voice_test_support import DummyRequest, create_job, create_test_env, run


def test_generate_endpoint_still_works(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)
    monkeypatch.setattr(api_routes, "dispatch_pipeline", Mock())

    async def _case():
        async with env.session_factory() as db:
            return await api_routes.generate.__wrapped__(
                request=DummyRequest(),
                req=GenerateRequest(
                    topic="Tema valido para verificar o fluxo legado", style="educational", duration_target=45
                ),
                user=env.verified_user,
                db=db,
            )

    response = run(_case())
    assert response["status"] == "queued"
    assert "job_id" in response


def test_edge_tts_still_works(tmp_path):
    output_path = tmp_path / "narration.wav"
    with patch("app.services.tts.edge_tts.Communicate") as mock_comm:
        instance = MagicMock()
        instance.save = AsyncMock(side_effect=lambda path: Path(path).write_bytes(b"audio"))
        mock_comm.return_value = instance
        result = synthesize_narration("texto legado", str(output_path), voice_id="pt-BR-AntonioNeural")
    assert result == str(output_path)
    assert output_path.exists()


def test_templates_endpoint_unchanged():
    response = run(api_routes.list_templates())
    template_ids = {item["id"] for item in response}
    assert template_ids == {
        "stock_narration",
        # Templates virais Q4 (2026-07-03): formatos do ICP de curiosidades.
        "curiosidades_lista",
        "voce_sabia",
        "gameplay_split",
        "character_narration",
        "story_time",
        "novelinha_historica",
        "ai_visual",
        "ai_video",
        "dialogue_duo",
    }


def test_templates_endpoint_exposes_pricing_metadata():
    response = run(api_routes.list_templates())
    novelinha = next(item for item in response if item["id"] == "novelinha_historica")
    assert novelinha["media_source"] == "ai_image"
    assert novelinha["default_voice_provider"] == "elevenlabs"
    assert novelinha["credit_costs"]["edge"] == 5
    assert novelinha["credit_costs"]["elevenlabs"] == 5


def test_job_status_format_unchanged(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)
    job = create_job(env)
    env.fake_redis.hset(
        f"job:{job.id}",
        mapping={
            "status": "processing",
            "progress": "0.5",
            "current_step": "tts",
            "error": "",
            "detail": "",
            "created_at": "2026-04-05T12:00:00+00:00",
        },
    )

    async def _case():
        async with env.session_factory() as db:
            return await api_routes.get_job(job_id=str(job.id), user=env.verified_user, db=db)

    response = run(_case())
    assert set(response.model_dump().keys()) == {
        "job_id",
        "status",
        "progress",
        "current_step",
        "error",
        "detail",
        "created_at",
        "download_url",
    }


def test_composition_endpoint_unchanged(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)
    job = create_job(env, script={"scenes": [{"text": "scene 1"}]}, editor_state=None)
    job_dir = env.storage_dir / "jobs" / str(job.id)
    (job_dir / "media").mkdir(parents=True)
    (job_dir / "script.json").write_text(json.dumps({"scenes": [{"text": "scene 1"}]}), encoding="utf-8")
    (job_dir / "words.json").write_text(json.dumps([{"word": "oi", "start": 0.0, "end": 0.5}]), encoding="utf-8")
    (job_dir / "narration.wav").write_bytes(b"audio")

    async def _case():
        async with env.session_factory() as db:
            return await api_routes.get_composition(job_id=str(job.id), user=env.verified_user, db=db)

    response = run(_case())
    assert set(response.model_dump().keys()) == {
        "job_id",
        "script",
        "words",
        "audio_url",
        "media_urls",
        "subtitle_style",
        "editor_state",
        "template_id",
        "layout_type",
        "fps",
        "width",
        "height",
        "pending_credits",
        "music_url",
        "music_volume",
    }


def test_editor_save_still_works(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)
    job = create_job(env, script={"scenes": [{"text": "scene 1"}]}, editor_state=None)
    job_dir = env.storage_dir / "jobs" / str(job.id)
    job_dir.mkdir(parents=True)
    request = DummyRequest(
        raw_body=json.dumps(
            {"editor_state": {"composition": {"scenes": [{"text": "editada"}], "words": [{"word": "oi"}]}}}
        ).encode()
    )

    async def _case():
        async with env.session_factory() as db:
            return await api_routes.save_editor_state(
                request=request, job_id=str(job.id), user=env.verified_user, db=db
            )

    response = run(_case())
    assert response["status"] == "saved"


def test_regenerate_tts_edge_default(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)
    job = create_job(env, script={"narration": "texto original", "scenes": []})
    job_dir = env.storage_dir / "jobs" / str(job.id)
    job_dir.mkdir(parents=True)
    (job_dir / "script.json").write_text(json.dumps({"narration": "texto original", "scenes": []}))
    synth_mock = AsyncMock(return_value=str(job_dir / "narration.wav"))
    monkeypatch.setattr("app.services.tts.synthesize_narration_async", synth_mock)
    monkeypatch.setattr("app.services.transcriber.transcribe_with_timestamps", lambda _path: [{"word": "ola"}])

    async def _case():
        async with env.session_factory() as db:
            return await api_routes.regenerate_tts(
                job_id=str(job.id),
                req=RegenerateTTSRequest(voice_id="pt-BR-AntonioNeural"),
                user=env.verified_user,
                db=db,
            )

    response = run(_case())
    assert response["audio_url"].split("?")[0].endswith("/narration.wav")
    synth_mock.assert_awaited_once()


def test_credits_debit_1_for_edge(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)
    monkeypatch.setattr(api_routes, "dispatch_pipeline", Mock())

    async def _case():
        async with env.session_factory() as db:
            before = (await db.get(User, env.verified_user.id)).credits
            response = await api_routes.generate.__wrapped__(
                request=DummyRequest(),
                req=GenerateRequest(
                    topic="Tema valido para verificar debito edge", style="educational", duration_target=45
                ),
                user=env.verified_user,
                db=db,
            )
            after = (await db.get(User, env.verified_user.id)).credits
            return before, after, response

    before, after, response = run(_case())
    assert response["credit_cost"] == 1
    assert before - after == 1


def test_render_endpoint_unchanged(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)
    job = create_job(env)
    (env.storage_dir / "jobs" / str(job.id)).mkdir(parents=True)
    delay_mock = Mock()
    monkeypatch.setattr("app.worker.tasks.task_rerender_video.delay", delay_mock)

    async def _case():
        async with env.session_factory() as db:
            return await api_routes.render_video(job_id=str(job.id), user=env.verified_user, db=db)

    response = run(_case())
    assert response["status"] == "rendering"
    delay_mock.assert_called_once_with(str(job.id))


def test_job_list_format_unchanged(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)
    job = create_job(env, status="queued")

    async def _case():
        async with env.session_factory() as db:
            return await api_routes.list_jobs(user=env.verified_user, db=db)

    response = run(_case())
    listed = next(item for item in response if item["job_id"] == str(job.id))
    assert set(listed.keys()) == {
        "job_id",
        "topic",
        "style",
        "status",
        "duration_target",
        "created_at",
        "download_url",
        # Grid reativa (2026-07-03): progresso em tempo real exposto do Redis.
        "progress",
        "current_step",
        # Q7 (2026-07-04): flag de degradacao do LLM (badge qualidade reduzida).
        "degraded",
    }
