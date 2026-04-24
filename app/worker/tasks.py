import asyncio
import json
import logging
import shutil
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from pathlib import Path

from celery.exceptions import SoftTimeLimitExceeded

from app.config import settings
from app.redis_pool import get_redis
from app.services.compositor import compose_short
from app.services.image_provider import ModerationBlockedError, OpenAIImageProvider
from app.services.media import download_media, search_media_for_scene
from app.services.scriptwriter import generate_script
from app.services.transcriber import transcribe_with_timestamps
from app.services.tts import synthesize_narration
from app.templates import get_template
from app.utils.files import bytes_to_gb, cleanup_job_dir, get_job_dir, get_output_dir, remove_path
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)

_redis = get_redis()


def _update_job(
    job_id: str,
    status: str,
    step: str | None = None,
    progress: float = 0.0,
    error: str | None = None,
    detail: str | None = None,
):
    data = {
        "status": status,
        "current_step": step or "",
        "progress": str(progress),
        "error": error or "",
        "detail": detail or "",
    }
    _redis.hset(f"job:{job_id}", mapping=data)


def _redis_get(key: str) -> str | None:
    getter = getattr(_redis, "get", None)
    return getter(key) if getter else None


def _redis_set(key: str, value: str) -> None:
    setter = getattr(_redis, "set", None)
    if setter:
        setter(key, value)


def _redis_hget(key: str, field: str) -> str | None:
    getter = getattr(_redis, "hget", None)
    if getter:
        return getter(key, field)
    return _redis.hgetall(key).get(field)


def _send_admin_alert(subject: str, message: str) -> None:
    if not settings.SMTP_HOST:
        return

    msg = MIMEText(message)
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = settings.SMTP_FROM

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
    except Exception:
        logger.exception("Failed to send admin alert email")


def _enqueue_dead_letter(job_id: str, error: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    _redis_set(f"failed_jobs:{job_id}", timestamp)
    _send_admin_alert(
        "ClipIA - job na dead letter queue",
        f"Job {job_id} entrou na fila de revisao em {timestamp}.\n\nErro: {error}",
    )


def _refund_job_credit(job_id: str, status_value: str, error: str, cleanup_files: bool = False):
    """Persist final state and refund the original generation credit once."""
    _update_job(job_id, status_value, error=error, detail=error)

    try:
        from sqlalchemy import select, update

        from app.db.engine import async_session
        from app.db.models import Job, User

        async def _refund():
            async with async_session() as session:
                result = await session.execute(select(Job).where(Job.id == job_id))
                job = result.scalar_one_or_none()
                if job:
                    if cleanup_files:
                        cleanup_job_dir(job_id)
                        remove_path(get_output_dir() / f"{job_id}.mp4")
                    if job.status in {"failed", "cancelled"}:
                        job.status = status_value
                        job.error = error
                        await session.commit()
                        return
                    job.status = status_value
                    job.error = error
                    refund_amount = job.credit_cost or 1
                    await session.execute(
                        update(User).where(User.id == job.user_id).values(credits=User.credits + refund_amount)
                    )
                    await session.commit()
                    logger.info("Refunded %d credit(s) for %s job %s", refund_amount, status_value, job_id)

        asyncio.run(_refund())
    except Exception as e:
        logger.error("Failed to refund credit for job %s: %s", job_id, e)


def _fail_job(job_id: str, error: str):
    """Mark job as failed, refund, and enqueue for review."""
    logger.exception("Job %s failed: %s", job_id, error)
    _refund_job_credit(job_id, "failed", error)
    _enqueue_dead_letter(job_id, error)


def _is_cancelled(job_id: str) -> bool:
    return _redis_get(f"job:{job_id}:cancelled") == "true"


def _cancel_job(job_id: str, detail: str = "Processamento cancelado pelo usuario.") -> None:
    logger.info("Job %s cancelled", job_id)
    _refund_job_credit(job_id, "cancelled", detail, cleanup_files=True)


def _check_cancelled(job_id: str) -> bool:
    if _is_cancelled(job_id):
        _cancel_job(job_id)
        return True
    return False


def _retry_or_fail(self, job_id: str, exc: Exception, message: str, countdowns: list[int]):
    attempt = int(getattr(getattr(self, "request", None), "retries", 0))
    if attempt < len(countdowns):
        countdown = countdowns[attempt]
        _update_job(job_id, "processing", progress=0.0, detail=f"{message} Tentando novamente em {countdown}s.")
        raise self.retry(exc=exc, countdown=countdown, max_retries=len(countdowns))
    _fail_job(job_id, message)
    raise exc


def _handle_soft_timeout(job_id: str, task_name: str):
    message = "Video demorou demais para gerar. Tente novamente."
    logger.error("Task %s exceeded soft time limit for job %s", task_name, job_id)
    _refund_job_credit(job_id, "failed", message)
    _enqueue_dead_letter(job_id, f"{task_name} soft timeout")


@celery_app.task(name="generate_images", bind=True)
def task_generate_images(self, data: dict, job_id: str, template_id: str) -> dict:
    try:
        if _check_cancelled(job_id):
            return data

        template = get_template(template_id)
        if template.media.source != "ai_image":
            logger.info("Job %s: template %s nao usa ai_image, skip", job_id, template_id)
            return data

        script = data.get("script")
        if not script:
            script_path = get_job_dir(job_id) / "script.json"
            script = json.loads(script_path.read_text(encoding="utf-8"))

        scenes = script.get("scenes", [])
        if not scenes:
            raise ValueError("Script sem cenas")

        _update_job(
            job_id,
            "processing",
            "generating_images",
            0.15,
            detail=f"Gerando {len(scenes)} imagens...",
        )

        quality = settings.GPT_IMAGE_QUALITY or template.media.image_quality
        provider = OpenAIImageProvider(
            quality=quality,
            size=template.media.image_size,
        )

        job_img_dir = get_job_dir(job_id) / "images"
        job_img_dir.mkdir(exist_ok=True, parents=True)

        image_paths: list[str] = []
        for i, scene in enumerate(scenes):
            if _check_cancelled(job_id):
                return data
            hint = scene.get("visual_hint", "").strip()
            if not hint:
                raise ValueError(f"cena {i+1} sem visual_hint")

            full_prompt = f"{hint}, {template.media.style_suffix}"
            out_path = job_img_dir / f"scene_{i+1}.png"
            provider.generate(full_prompt, out_path)

            image_paths.append(str(out_path))
            progress = 0.15 + (0.15 * (i + 1) / len(scenes))
            _update_job(
                job_id,
                "processing",
                "generating_images",
                progress,
                detail=f"Imagem {i+1}/{len(scenes)} OK",
            )

        data["image_paths"] = image_paths
        return data

    except SoftTimeLimitExceeded:
        _handle_soft_timeout(job_id, "generate_images")
        raise
    except ModerationBlockedError as e:
        _fail_job(job_id, f"Conteudo bloqueado pela moderacao: {e}")
        raise
    except Exception as e:
        _fail_job(job_id, f"Falha ao gerar imagens: {e}")
        raise


def dispatch_pipeline(
    job_id: str,
    topic: str,
    style: str,
    duration_target: int,
    template_id: str = "stock_narration",
    voice_provider: str = "edge",
    voice_config: dict | None = None,
):
    from celery import chain

    _redis.hset(
        f"job:{job_id}",
        mapping={
            "status": "queued",
            "current_step": "",
            "progress": "0",
            "error": "",
            "detail": "",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "template_id": template_id,
            "voice_provider": voice_provider,
        },
    )
    # Store voice config in Redis for the worker to pick up
    if voice_config:
        _redis.hset(f"job:{job_id}", mapping={"voice_config": json.dumps(voice_config)})

    pipeline = chain(
        task_generate_script.s(job_id, topic, style, duration_target, template_id),
        task_generate_images.s(job_id, template_id),
        task_synthesize_audio.s(job_id, template_id),
        task_transcribe_audio.s(job_id),
        task_fetch_media.s(job_id, template_id),
        task_compose_video.s(job_id, template_id),
        task_finalize.s(job_id),
    )
    pipeline.apply_async()


async def _cleanup_old_jobs_async() -> dict[str, int]:
    from sqlalchemy import select

    from app.db.engine import async_session
    from app.db.models import Job

    now = datetime.now(timezone.utc)
    failed_cutoff = now - timedelta(days=7)
    completed_cutoff = now - timedelta(days=30)

    total_reclaimed = 0
    removed_jobs = 0
    removed_outputs = 0

    async with async_session() as session:
        result = await session.execute(
            select(Job).where(
                ((Job.status == "failed") & (Job.created_at <= failed_cutoff))
                | ((Job.status.in_(("completed", "editable"))) & (Job.created_at <= completed_cutoff))
            )
        )
        jobs = result.scalars().all()

        for job in jobs:
            job_dir = settings.STORAGE_DIR / "jobs" / str(job.id)
            output_path = settings.STORAGE_DIR / "output" / f"{job.id}.mp4"
            if output_path.exists():
                removed_outputs += 1
            total_reclaimed += remove_path(job_dir)
            total_reclaimed += remove_path(output_path)
            if job.video_url is not None:
                job.video_url = None
            removed_jobs += 1

        await session.commit()

    logger.info(
        "cleanup_old_jobs removed %s jobs and reclaimed %.2f GB",
        removed_jobs,
        bytes_to_gb(total_reclaimed),
    )
    return {"removed_jobs": removed_jobs, "removed_outputs": removed_outputs, "reclaimed_bytes": total_reclaimed}


async def _cleanup_orphan_files_async() -> dict[str, int]:
    from sqlalchemy import select

    from app.db.engine import async_session
    from app.db.models import Job

    total_reclaimed = 0
    removed_dirs = 0
    removed_outputs = 0

    jobs_dir = settings.STORAGE_DIR / "jobs"
    output_dir = settings.STORAGE_DIR / "output"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    async with async_session() as session:
        result = await session.execute(select(Job.id))
        job_ids = {str(job_id) for job_id in result.scalars().all()}

    for entry in jobs_dir.iterdir():
        if entry.is_dir() and entry.name not in job_ids:
            total_reclaimed += remove_path(entry)
            removed_dirs += 1

    for entry in output_dir.glob("*.mp4"):
        if entry.stem not in job_ids:
            total_reclaimed += remove_path(entry)
            removed_outputs += 1

    logger.info(
        "cleanup_orphan_files removed %s dirs and %s outputs, reclaimed %.2f GB",
        removed_dirs,
        removed_outputs,
        bytes_to_gb(total_reclaimed),
    )
    return {"removed_dirs": removed_dirs, "removed_outputs": removed_outputs, "reclaimed_bytes": total_reclaimed}


@celery_app.task(name="cleanup_old_jobs")
def cleanup_old_jobs() -> dict[str, int]:
    return asyncio.run(_cleanup_old_jobs_async())


@celery_app.task(name="cleanup_orphan_files")
def cleanup_orphan_files() -> dict[str, int]:
    return asyncio.run(_cleanup_orphan_files_async())


@celery_app.task(name="generate_script", bind=True)
def task_generate_script(
    self, job_id: str, topic: str, style: str, duration_target: int, template_id: str = "stock_narration"
) -> dict:
    try:
        if _check_cancelled(job_id):
            return {"cancelled": True}
        _update_job(job_id, "processing", "scripting", 0.1, detail="Gerando roteiro com IA...")
        script = generate_script(topic, style, duration_target, template_id=template_id)
        job_dir = get_job_dir(job_id)
        (job_dir / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=2))

        # Validate script
        scenes = script.get("scenes", [])
        if not scenes:
            raise ValueError("Script has no scenes")
        total_dur = sum(s.get("duration_hint", 7) for s in scenes)
        logger.info(
            f"Script: {len(scenes)} scenes, {total_dur}s total, {len(script.get('narration', '').split())} words"
        )

        _update_job(job_id, "processing", "scripting", 0.16, detail="Roteiro gerado com sucesso.")
        script["_duration_target"] = duration_target
        return script
    except SoftTimeLimitExceeded:
        _handle_soft_timeout(job_id, "generate_script")
        raise
    except Exception as e:
        _retry_or_fail(self, job_id, e, f"Script generation failed: {e}", [10, 30])


@celery_app.task(name="synthesize_audio", bind=True)
def task_synthesize_audio(self, script: dict, job_id: str, template_id: str = "stock_narration") -> str:
    try:
        if isinstance(script, dict) and script.get("cancelled"):
            return ""
        if _check_cancelled(job_id):
            return ""

        _update_job(job_id, "processing", "tts", 0.25, detail="Sintetizando narracao...")
        job_dir = get_job_dir(job_id)
        output_path = str(job_dir / "narration.wav")
        duration_target = script.get("_duration_target", 0)

        # Check if job has custom voice config (v2) or use template default
        voice_provider_name = _redis_hget(f"job:{job_id}", "voice_provider") or "edge"
        voice_config_raw = _redis_hget(f"job:{job_id}", "voice_config")
        voice_config = json.loads(voice_config_raw) if voice_config_raw else None

        if voice_provider_name == "custom":
            # Custom audio — just copy the uploaded file (already validated)
            uploaded_path = voice_config.get("source_path", "") if voice_config else ""
            if uploaded_path and Path(uploaded_path).exists():
                from app.services.custom_audio_provider import normalize_audio

                normalize_audio(uploaded_path, output_path)
            else:
                raise RuntimeError("Custom audio source not found")
        elif voice_provider_name == "elevenlabs":
            # ElevenLabs premium TTS
            from app.services.elevenlabs_provider import ElevenLabsProvider

            provider = ElevenLabsProvider()
            voice_id = voice_config.get("voice_id", "") if voice_config else ""
            if not voice_id:
                raise RuntimeError("No ElevenLabs voice_id specified")
            asyncio.run(
                provider.synthesize(
                    text=script["narration"],
                    output_path=output_path,
                    voice_id=voice_id,
                    duration_target=duration_target,
                )
            )
        else:
            # Edge TTS (default, free)
            from app.templates import get_template

            template = get_template(template_id)
            voice_id = (voice_config or {}).get("voice_id", template.voice.voice_id)
            rate = (voice_config or {}).get("rate", template.voice.rate)
            pitch = (voice_config or {}).get("pitch", template.voice.pitch)
            synthesize_narration(
                text=script["narration"],
                output_path=output_path,
                duration_target=duration_target,
                voice_id=voice_id,
                rate=rate,
                pitch=pitch,
            )

        # Validate audio exists and has reasonable duration
        if not Path(output_path).exists():
            raise RuntimeError("TTS produced no output file")
        size = Path(output_path).stat().st_size
        if size < 10000:  # < 10KB = probably empty/corrupt
            raise RuntimeError(f"TTS output too small ({size} bytes)")

        _update_job(job_id, "processing", "tts", 0.35, detail="Validando audio...")
        _update_job(job_id, "processing", "tts", 0.4, detail="Narracao pronta.")
        logger.info(f"TTS output: {size / 1024:.0f}KB (provider={voice_provider_name})")
        return output_path
    except SoftTimeLimitExceeded:
        _handle_soft_timeout(job_id, "synthesize_audio")
        raise
    except Exception as e:
        _retry_or_fail(self, job_id, e, f"TTS failed: {e}", [5, 15])


@celery_app.task(name="transcribe_audio", bind=True)
def task_transcribe_audio(self, audio_path: str, job_id: str) -> dict:
    try:
        if not audio_path or _check_cancelled(job_id):
            return {"cancelled": True}
        _update_job(job_id, "processing", "transcribing", 0.45, detail="Transcrevendo com Whisper...")
        words = transcribe_with_timestamps(audio_path)
        job_dir = get_job_dir(job_id)
        (job_dir / "words.json").write_text(json.dumps(words, ensure_ascii=False))
        script = json.loads((job_dir / "script.json").read_text())

        if not words:
            raise RuntimeError("Whisper produced no word timestamps")

        logger.info(f"Transcription: {len(words)} words, last word at {words[-1]['end']:.1f}s")
        _update_job(job_id, "processing", "transcribing", 0.5, detail="Transcricao concluida.")
        return {"words": words, "script": script, "audio_path": audio_path}
    except SoftTimeLimitExceeded:
        _handle_soft_timeout(job_id, "transcribe_audio")
        raise
    except Exception as e:
        _fail_job(job_id, f"Transcription failed: {e}")
        raise


@celery_app.task(name="fetch_media", bind=True)
def task_fetch_media(self, data: dict, job_id: str, template_id: str = "stock_narration") -> dict:
    try:
        if data.get("cancelled") or _check_cancelled(job_id):
            return {"cancelled": True}
        from app.services.media_library import pick_clip
        from app.templates import get_template

        template = get_template(template_id)
        if template.media.source == "ai_image":
            image_paths = data.get("image_paths")
            if not image_paths:
                img_dir = get_job_dir(job_id) / "images"
                image_paths = sorted(str(p) for p in img_dir.glob("scene_*.png"))
            data["media_paths"] = image_paths
            _update_job(job_id, "processing", "media", 0.65, detail="Imagens IA ja geradas, skip Pexels.")
            return data
        _update_job(job_id, "processing", "media", 0.55, detail="Buscando videos...")
        script = data["script"]
        job_dir = get_job_dir(job_id)
        media_dir = job_dir / "media"
        media_dir.mkdir(exist_ok=True)

        media_paths = []

        if template.media.source == "local" and template.media.loop_single:
            # Single local clip, looped for entire video
            clip = pick_clip(template.media.library_tag or "minecraft_parkour")
            if clip is None:
                raise RuntimeError(f"No clips in library '{template.media.library_tag}'")
            dest = str(media_dir / "background.mp4")
            shutil.copy2(str(clip), dest)
            media_paths = [dest]
            logger.info(f"Using local clip: {clip.name} (will loop)")
        else:
            # Original Pexels behavior (per-scene search)
            for i, scene in enumerate(script["scenes"]):
                if _check_cancelled(job_id):
                    return {"cancelled": True}
                keywords = scene.get("keywords_en", ["nature"])
                _update_job(
                    job_id,
                    "processing",
                    "media",
                    0.55,
                    detail=f"Buscando videos (cena {i + 1}/{len(script['scenes'])})...",
                )
                results = asyncio.run(search_media_for_scene(keywords))
                if results:
                    dest = str(media_dir / f"scene_{i}.mp4")
                    try:
                        asyncio.run(download_media(results[0]["url"], dest))
                        media_paths.append(dest)
                        logger.info(f"Scene {i}: downloaded '{keywords[0]}'")
                    except Exception as e:
                        logger.warning(f"Scene {i}: download failed, trying next result: {e}")
                        if len(results) > 1:
                            try:
                                asyncio.run(download_media(results[1]["url"], dest))
                                media_paths.append(dest)
                            except Exception:
                                logger.error(f"Scene {i}: all downloads failed")
                else:
                    logger.warning(f"Scene {i}: no media found for {keywords}")

        if not media_paths:
            raise RuntimeError("No media available")

        logger.info(f"Media: {len(media_paths)} file(s) ready")
        _update_job(job_id, "processing", "media", 0.65, detail="Midias prontas.")
        data["media_paths"] = media_paths
        return data
    except SoftTimeLimitExceeded:
        _handle_soft_timeout(job_id, "fetch_media")
        raise
    except Exception as e:
        _retry_or_fail(self, job_id, e, f"Media fetch failed: {e}", [10, 30, 60])


@celery_app.task(name="compose_video", bind=True)
def task_compose_video(self, data: dict, job_id: str, template_id: str = "stock_narration") -> str:
    try:
        if data.get("cancelled") or _check_cancelled(job_id):
            return ""
        from app.templates import get_template

        template = get_template(template_id)

        _update_job(job_id, "processing", "compositing", 0.7, detail="Montando video com FFmpeg...")
        job_dir = get_job_dir(job_id)
        output_path = str(job_dir / "final.mp4")
        compose_short(
            scenes=data["script"]["scenes"],
            media_paths=data["media_paths"],
            audio_path=data["audio_path"],
            words=data["words"],
            output_path=output_path,
            layout=template.layout,
        )
        _update_job(job_id, "processing", "compositing", 0.9, detail="Video montado.")
        return output_path
    except SoftTimeLimitExceeded:
        _handle_soft_timeout(job_id, "compose_video")
        raise
    except Exception as e:
        _fail_job(job_id, f"Compositing failed: {e}")
        raise


@celery_app.task(name="finalize", bind=True)
def task_finalize(self, video_path: str, job_id: str) -> str:
    try:
        if not video_path or _check_cancelled(job_id):
            return ""
        _update_job(job_id, "processing", "finalizing", 0.95, detail="Salvando video final...")
        output_dir = get_output_dir()
        final_path = str(output_dir / f"{job_id}.mp4")
        shutil.copy2(video_path, final_path)

        # Save script to PostgreSQL for the editor (keep job dir for editing)
        try:
            from sqlalchemy import update

            from app.db.engine import async_session
            from app.db.models import Job

            job_dir = get_job_dir(job_id)
            script_path = job_dir / "script.json"
            script_data = json.loads(script_path.read_text()) if script_path.exists() else None

            async def _save_script():
                async with async_session() as session:
                    await session.execute(
                        update(Job)
                        .where(Job.id == job_id)
                        .values(
                            script=script_data,
                            status="editable",
                            video_url=final_path,
                        )
                    )
                    await session.commit()

            asyncio.run(_save_script())
        except Exception as e:
            logger.warning(f"Could not save script to DB: {e}")

        _update_job(job_id, "completed", None, 1.0, detail="Video final pronto para download.")
        return final_path
    except SoftTimeLimitExceeded:
        _handle_soft_timeout(job_id, "finalize")
        raise
    except Exception as e:
        _fail_job(job_id, f"Finalize failed: {e}")
        raise


@celery_app.task(name="rerender_video", bind=True, soft_time_limit=90, time_limit=120)
def task_rerender_video(self, job_id: str) -> str:
    """Re-render video with editor changes using FFmpeg + NVENC (~15s).

    Runs in background — user never waits. Previous version stays available.
    """
    try:
        if _check_cancelled(job_id):
            return ""
        _update_job(job_id, "rendering", "preparing", 0.05, detail="Preparando arquivos para re-render...")
        job_dir = get_job_dir(job_id)
        from app.config import BASE_DIR
        from app.services.compositor import compose_short

        script_path = job_dir / "script.json"
        if not script_path.exists():
            raise RuntimeError("script.json not found")
        script = json.loads(script_path.read_text())

        words_path = job_dir / "words.json"
        words = json.loads(words_path.read_text()) if words_path.exists() else []

        audio_path = str(job_dir / "narration.wav")
        if not Path(audio_path).exists():
            raise RuntimeError("narration.wav not found")

        # Collect media file paths
        media_paths = []
        media_dir = job_dir / "media"
        if media_dir.exists():
            # Check for local template background first
            bg_file = media_dir / "background.mp4"
            if bg_file.exists():
                media_paths = [str(bg_file)]
            else:
                for i in range(len(script.get("scenes", []))):
                    scene_file = media_dir / f"scene_{i}.mp4"
                    if scene_file.exists():
                        media_paths.append(str(scene_file))

        if not media_paths:
            raise RuntimeError("No media files found for re-render")

        # Read editor_state
        editor_state_path = job_dir / "editor_state.json"
        comp_data = {}
        if editor_state_path.exists():
            editor_state = json.loads(editor_state_path.read_text())
            comp_data = editor_state.get("composition", {})

        # Resolve music path
        music_path = None
        music_url = comp_data.get("musicUrl")
        if music_url:
            music_file = BASE_DIR / "frontend" / "public" / music_url.lstrip("/")
            if music_file.exists():
                music_path = str(music_file)

        output_path = str(job_dir / "final_edited.mp4")

        _update_job(job_id, "rendering", "encoding", 0.2, detail="Re-renderizando video...")
        logger.info(f"Starting FFmpeg+NVENC re-render for job {job_id}")

        # Get template layout for re-render
        from app.templates import get_template

        re_template_id = _redis_hget(f"job:{job_id}", "template_id") or "stock_narration"
        re_template = get_template(re_template_id)

        compose_short(
            scenes=script.get("scenes", []),
            media_paths=media_paths,
            audio_path=audio_path,
            words=words,
            output_path=output_path,
            music_path=music_path,
            music_volume=comp_data.get("musicVolume", 0.15),
            subtitle_style=comp_data.get("subtitleStyle"),
            layout=re_template.layout,
        )

        _update_job(job_id, "rendering", "finalizing", 0.9, detail="Finalizando re-render...")

        # Copy to output dir (becomes downloadable version)
        output_dir = get_output_dir()
        final_path = str(output_dir / f"{job_id}.mp4")
        shutil.copy2(output_path, final_path)

        _update_job(job_id, "completed", None, 1.0, detail="Re-render concluido.")
        logger.info(f"Re-render completed for job {job_id}")
        return final_path
    except SoftTimeLimitExceeded:
        _handle_soft_timeout(job_id, "rerender_video")
        raise
    except Exception as e:
        _update_job(job_id, "error", error=str(e), detail=str(e))
        logger.error(f"Re-render failed for job {job_id}: {e}")
        raise
