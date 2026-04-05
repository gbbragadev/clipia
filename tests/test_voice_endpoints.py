from __future__ import annotations

import json
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api import routes as api_routes
from app.auth.dependencies import get_current_user
from app.db.models import Job, User
from app.models import GenerateRequest, RegenerateTTSRequest, VoiceCloneRequest
from tests.voice_test_support import (
    DummyForm,
    DummyRequest,
    DummyUpload,
    create_clone,
    create_job,
    create_test_env,
    run,
)


def test_list_voices_authenticated(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)
    monkeypatch.setattr("app.api.routes.settings.ELEVENLABS_API_KEY", "")

    async def _case():
        async with env.session_factory() as db:
            return await api_routes.list_voices(user=env.verified_user, db=db)

    voices = run(_case())
    assert len(voices) >= 3
    assert {voice["provider"] for voice in voices} == {"edge"}


def test_list_voices_unauthenticated(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)

    async def _case():
        async with env.session_factory() as db:
            return await get_current_user(
                credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid"),
                db=db,
            )

    with pytest.raises(HTTPException) as exc:
        run(_case())
    assert exc.value.status_code == 401


def test_list_voices_includes_user_clones(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)
    clone = create_clone(env)
    monkeypatch.setattr("app.api.routes.settings.ELEVENLABS_API_KEY", "")

    async def _case():
        async with env.session_factory() as db:
            return await api_routes.list_voices(user=env.verified_user, db=db)

    voices = run(_case())
    assert any(voice.get("clone_id") == str(clone.id) and voice.get("is_clone") for voice in voices)


def test_clone_voice_success(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)
    monkeypatch.setattr("app.api.routes.settings.ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setattr(
        "app.services.elevenlabs_provider.ElevenLabsProvider.clone_voice", AsyncMock(return_value="cloned_voice_1")
    )

    async def _case():
        async with env.session_factory() as db:
            return await api_routes.clone_voice.__wrapped__(
                request=DummyRequest(form=DummyForm(files=[DummyUpload("sample.wav", b"wav")])),
                req=VoiceCloneRequest(name="Minha voz", description="Amostra"),
                user=env.verified_user,
                db=db,
            )

    payload = run(_case())
    assert payload["voice_id"] == "cloned_voice_1"


def test_clone_voice_no_files(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)
    monkeypatch.setattr("app.api.routes.settings.ELEVENLABS_API_KEY", "test-key")

    async def _case():
        async with env.session_factory() as db:
            return await api_routes.clone_voice.__wrapped__(
                request=DummyRequest(),
                req=VoiceCloneRequest(name="Minha voz"),
                user=env.verified_user,
                db=db,
            )

    with pytest.raises(HTTPException) as exc:
        run(_case())
    assert exc.value.status_code == 400


def test_clone_voice_max_limit(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)
    monkeypatch.setattr("app.api.routes.settings.ELEVENLABS_API_KEY", "test-key")
    for idx in range(5):
        create_clone(env, name=f"Clone {idx}", external_voice_id=f"clone_{idx}")

    async def _case():
        async with env.session_factory() as db:
            return await api_routes.clone_voice.__wrapped__(
                request=DummyRequest(form=DummyForm(files=[DummyUpload("sample.wav", b"wav")])),
                req=VoiceCloneRequest(name="Excesso"),
                user=env.verified_user,
                db=db,
            )

    with pytest.raises(HTTPException) as exc:
        run(_case())
    assert exc.value.status_code == 400
    assert "Máximo de 5 vozes" in exc.value.detail


def test_clone_voice_unauthenticated(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)

    async def _case():
        async with env.session_factory() as db:
            return await get_current_user(
                credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid"),
                db=db,
            )

    with pytest.raises(HTTPException) as exc:
        run(_case())
    assert exc.value.status_code == 401


def test_clone_voice_no_elevenlabs_key(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)
    monkeypatch.setattr("app.api.routes.settings.ELEVENLABS_API_KEY", "")

    async def _case():
        async with env.session_factory() as db:
            return await api_routes.clone_voice.__wrapped__(
                request=DummyRequest(form=DummyForm(files=[DummyUpload("sample.wav", b"wav")])),
                req=VoiceCloneRequest(name="Minha voz"),
                user=env.verified_user,
                db=db,
            )

    with pytest.raises(HTTPException) as exc:
        run(_case())
    assert exc.value.status_code == 503


def test_delete_clone_success(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)
    clone = create_clone(env)
    monkeypatch.setattr("app.api.routes.settings.ELEVENLABS_API_KEY", "test-key")
    delete_mock = AsyncMock()
    monkeypatch.setattr("app.services.elevenlabs_provider.ElevenLabsProvider.delete_voice", delete_mock)

    async def _case():
        async with env.session_factory() as db:
            return await api_routes.delete_voice(clone_id=str(clone.id), user=env.verified_user, db=db)

    payload = run(_case())
    assert payload["status"] == "deleted"
    delete_mock.assert_awaited_once_with("el_clone_123")


def test_delete_clone_not_found(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)

    async def _case():
        async with env.session_factory() as db:
            return await api_routes.delete_voice(
                clone_id="5fd8df17-5ac6-40d8-a0e5-c4d2b0ebef63",
                user=env.verified_user,
                db=db,
            )

    with pytest.raises(HTTPException) as exc:
        run(_case())
    assert exc.value.status_code == 404


def test_delete_clone_other_user(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)
    clone = create_clone(env, user_id=env.other_verified_user.id, name="Outra voz", external_voice_id="other_voice")

    async def _case():
        async with env.session_factory() as db:
            return await api_routes.delete_voice(clone_id=str(clone.id), user=env.verified_user, db=db)

    with pytest.raises(HTTPException) as exc:
        run(_case())
    assert exc.value.status_code == 404


def test_upload_audio_success(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)
    job = create_job(env)
    monkeypatch.setattr(
        "app.services.custom_audio_provider.validate_audio_file",
        lambda _path: {"duration": 10.5, "size_bytes": 1024, "format": "wav"},
    )
    normalize_mock = Mock()
    monkeypatch.setattr("app.services.custom_audio_provider.normalize_audio", normalize_mock)
    monkeypatch.setattr("app.services.transcriber.transcribe_with_timestamps", lambda _path: [{"word": "ola"}])

    async def _case():
        async with env.session_factory() as db:
            return await api_routes.upload_audio.__wrapped__(
                request=DummyRequest(form=DummyForm(file=DummyUpload("audio.wav", b"audio"))),
                job_id=str(job.id),
                user=env.verified_user,
                db=db,
            )

    payload = run(_case())
    assert payload["audio_url"].endswith("/narration.wav")
    assert payload["words"] == [{"word": "ola"}]
    normalize_mock.assert_called_once()


def test_upload_audio_too_large(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)
    job = create_job(env)

    async def _case():
        async with env.session_factory() as db:
            return await api_routes.upload_audio.__wrapped__(
                request=DummyRequest(form=DummyForm(file=DummyUpload("audio.wav", b"x" * (50 * 1024 * 1024 + 1)))),
                job_id=str(job.id),
                user=env.verified_user,
                db=db,
            )

    with pytest.raises(HTTPException) as exc:
        run(_case())
    assert exc.value.status_code == 400


def test_upload_audio_no_file(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)
    job = create_job(env)

    async def _case():
        async with env.session_factory() as db:
            return await api_routes.upload_audio.__wrapped__(
                request=DummyRequest(),
                job_id=str(job.id),
                user=env.verified_user,
                db=db,
            )

    with pytest.raises(HTTPException) as exc:
        run(_case())
    assert exc.value.status_code == 400


def test_upload_audio_validates_format(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)
    job = create_job(env)
    monkeypatch.setattr(
        "app.services.custom_audio_provider.validate_audio_file",
        lambda _path: (_ for _ in ()).throw(ValueError("Formato de áudio não reconhecido")),
    )

    async def _case():
        async with env.session_factory() as db:
            return await api_routes.upload_audio.__wrapped__(
                request=DummyRequest(form=DummyForm(file=DummyUpload("audio.wav", b"audio"))),
                job_id=str(job.id),
                user=env.verified_user,
                db=db,
            )

    with pytest.raises(HTTPException) as exc:
        run(_case())
    assert exc.value.status_code == 400
    assert "Formato de áudio não reconhecido" in exc.value.detail


def test_upload_audio_unauthenticated(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)

    async def _case():
        async with env.session_factory() as db:
            return await get_current_user(
                credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid"),
                db=db,
            )

    with pytest.raises(HTTPException) as exc:
        run(_case())
    assert exc.value.status_code == 401


def test_generate_with_edge_costs_1_credit(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)
    monkeypatch.setattr(api_routes, "dispatch_pipeline", Mock())

    async def _case():
        async with env.session_factory() as db:
            before = (await db.get(User, env.verified_user.id)).credits
            response = await api_routes.generate.__wrapped__(
                request=DummyRequest(),
                req=GenerateRequest(
                    topic="Tema valido para video edge provider",
                    style="educational",
                    duration_target=45,
                    voice_provider="edge",
                ),
                user=env.verified_user,
                db=db,
            )
            after = (await db.get(User, env.verified_user.id)).credits
            return before, after, response

    before, after, response = run(_case())
    assert response["credit_cost"] == 1
    assert before - after == 1


def test_generate_with_elevenlabs_costs_2_credits(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)
    monkeypatch.setattr(api_routes, "dispatch_pipeline", Mock())

    async def _case():
        async with env.session_factory() as db:
            before = (await db.get(User, env.verified_user.id)).credits
            response = await api_routes.generate.__wrapped__(
                request=DummyRequest(),
                req=GenerateRequest(
                    topic="Tema valido para video premium elevenlabs",
                    style="educational",
                    duration_target=45,
                    voice_provider="elevenlabs",
                    voice_config={"voice_id": "el_123"},
                ),
                user=env.verified_user,
                db=db,
            )
            after = (await db.get(User, env.verified_user.id)).credits
            return before, after, response

    before, after, response = run(_case())
    assert response["credit_cost"] == 2
    assert before - after == 2


def test_generate_with_elevenlabs_insufficient_credits(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)
    monkeypatch.setattr(api_routes, "dispatch_pipeline", Mock())

    async def _case():
        async with env.session_factory() as db:
            user = await db.get(User, env.verified_user.id)
            user.credits = 1
            await db.commit()
            return await api_routes.generate.__wrapped__(
                request=DummyRequest(),
                req=GenerateRequest(
                    topic="Tema valido para video premium elevenlabs",
                    style="educational",
                    duration_target=45,
                    voice_provider="elevenlabs",
                    voice_config={"voice_id": "el_123"},
                ),
                user=env.verified_user,
                db=db,
            )

    with pytest.raises(HTTPException) as exc:
        run(_case())
    assert exc.value.status_code == 402


def test_generate_passes_voice_config_to_redis(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)
    redis_calls = []

    def fake_dispatch(
        job_id,
        _topic,
        _style,
        _duration_target,
        template_id="stock_narration",
        voice_provider="edge",
        voice_config=None,
    ):
        redis_calls.append((job_id, template_id, voice_provider, voice_config))

    monkeypatch.setattr(api_routes, "dispatch_pipeline", fake_dispatch)

    async def _case():
        async with env.session_factory() as db:
            return await api_routes.generate.__wrapped__(
                request=DummyRequest(),
                req=GenerateRequest(
                    topic="Tema valido para video premium elevenlabs",
                    style="educational",
                    duration_target=45,
                    voice_provider="elevenlabs",
                    voice_config={"voice_id": "el_abc123"},
                ),
                user=env.verified_user,
                db=db,
            )

    response = run(_case())
    assert redis_calls[0][2] == "elevenlabs"
    assert redis_calls[0][3] == {"voice_id": "el_abc123"}
    assert response["status"] == "queued"


def test_generate_backwards_compatible(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)
    monkeypatch.setattr(api_routes, "dispatch_pipeline", Mock())

    async def _case():
        async with env.session_factory() as db:
            before = (await db.get(User, env.verified_user.id)).credits
            response = await api_routes.generate.__wrapped__(
                request=DummyRequest(),
                req=GenerateRequest(
                    topic="Tema valido para fluxo antigo compatível", style="educational", duration_target=45
                ),
                user=env.verified_user,
                db=db,
            )
            after = (await db.get(User, env.verified_user.id)).credits
            job = await db.get(Job, response["job_id"])
            return before, after, response, job

    before, after, response, job = run(_case())
    assert response["credit_cost"] == 1
    assert job.voice_provider == "edge"
    assert before - after == 1


def test_regenerate_tts_with_edge(tmp_path, monkeypatch):
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
                req=RegenerateTTSRequest(voice_provider="edge", voice_id="pt-BR-AntonioNeural"),
                user=env.verified_user,
                db=db,
            )

    payload = run(_case())
    assert payload["audio_url"].endswith("/narration.wav")
    synth_mock.assert_awaited_once()


def test_regenerate_tts_with_elevenlabs(tmp_path, monkeypatch):
    env = create_test_env(tmp_path, monkeypatch)
    job = create_job(env, script={"narration": "texto original", "scenes": []})
    job_dir = env.storage_dir / "jobs" / str(job.id)
    job_dir.mkdir(parents=True)
    (job_dir / "script.json").write_text(json.dumps({"narration": "texto original", "scenes": []}))
    synth_mock = AsyncMock(return_value=job_dir / "narration.wav")
    monkeypatch.setattr("app.api.routes.settings.ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setattr("app.services.elevenlabs_provider.ElevenLabsProvider.synthesize", synth_mock)
    monkeypatch.setattr("app.services.transcriber.transcribe_with_timestamps", lambda _path: [{"word": "ola"}])

    async def _case():
        async with env.session_factory() as db:
            return await api_routes.regenerate_tts(
                job_id=str(job.id),
                req=RegenerateTTSRequest(voice_provider="elevenlabs", voice_id="el_123"),
                user=env.verified_user,
                db=db,
            )

    payload = run(_case())
    assert payload["audio_url"].endswith("/narration.wav")
    synth_mock.assert_awaited_once()
