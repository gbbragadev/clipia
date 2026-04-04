import asyncio
import json
import logging
import shutil
from datetime import datetime, timezone

import redis

from app.config import settings
from app.services.compositor import compose_short
from app.services.media import download_media, search_media_for_scene
from app.services.scriptwriter import generate_script
from app.services.transcriber import transcribe_with_timestamps
from app.services.tts import synthesize_narration
from app.utils.files import cleanup_job_dir, get_job_dir, get_output_dir
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)

_redis = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


def _update_job(job_id: str, status: str, step: str | None = None, progress: float = 0.0, error: str | None = None):
    data = {"status": status, "current_step": step or "", "progress": str(progress), "error": error or ""}
    _redis.hset(f"job:{job_id}", mapping=data)


def _fail_job(job_id: str, error: str):
    """Mark job as failed and attempt credit refund."""
    logger.error(f"Job {job_id} failed: {error}")
    _update_job(job_id, "error", error=error)

    # Refund credit in PostgreSQL
    try:
        from sqlalchemy import select, update
        from app.db.engine import async_session
        from app.db.models import Job, User

        async def _refund():
            async with async_session() as session:
                result = await session.execute(select(Job).where(Job.id == job_id))
                job = result.scalar_one_or_none()
                if job:
                    job.status = "failed"
                    job.error = error
                    await session.execute(
                        update(User).where(User.id == job.user_id).values(credits=User.credits + 1)
                    )
                    await session.commit()
                    logger.info(f"Refunded 1 credit for failed job {job_id}")

        asyncio.run(_refund())
    except Exception as e:
        logger.error(f"Failed to refund credit for job {job_id}: {e}")


def dispatch_pipeline(job_id: str, topic: str, style: str, duration_target: int):
    from celery import chain

    _redis.hset(f"job:{job_id}", mapping={
        "status": "queued",
        "current_step": "",
        "progress": "0",
        "error": "",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    pipeline = chain(
        task_generate_script.s(job_id, topic, style, duration_target),
        task_synthesize_audio.s(job_id),
        task_transcribe_audio.s(job_id),
        task_fetch_media.s(job_id),
        task_compose_video.s(job_id),
        task_finalize.s(job_id),
    )
    pipeline.apply_async()


@celery_app.task(name="generate_script", bind=True)
def task_generate_script(self, job_id: str, topic: str, style: str, duration_target: int) -> dict:
    try:
        _update_job(job_id, "processing", "scripting", 0.1)
        script = generate_script(topic, style, duration_target)
        job_dir = get_job_dir(job_id)
        (job_dir / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=2))

        # Validate script
        scenes = script.get("scenes", [])
        if not scenes:
            raise ValueError("Script has no scenes")
        total_dur = sum(s.get("duration_hint", 7) for s in scenes)
        logger.info(f"Script: {len(scenes)} scenes, {total_dur}s total, {len(script.get('narration', '').split())} words")

        _update_job(job_id, "processing", "scripting", 0.16)
        script["_duration_target"] = duration_target
        return script
    except Exception as e:
        _fail_job(job_id, f"Script generation failed: {e}")
        raise


@celery_app.task(name="synthesize_audio", bind=True)
def task_synthesize_audio(self, script: dict, job_id: str) -> str:
    try:
        _update_job(job_id, "processing", "tts", 0.2)
        job_dir = get_job_dir(job_id)
        output_path = str(job_dir / "narration.wav")
        duration_target = script.get("_duration_target", 0)
        synthesize_narration(text=script["narration"], output_path=output_path, duration_target=duration_target)

        # Validate audio exists and has reasonable duration
        from pathlib import Path
        if not Path(output_path).exists():
            raise RuntimeError("TTS produced no output file")
        size = Path(output_path).stat().st_size
        if size < 10000:  # < 10KB = probably empty/corrupt
            raise RuntimeError(f"TTS output too small ({size} bytes)")

        _update_job(job_id, "processing", "tts", 0.4)
        logger.info(f"TTS output: {size / 1024:.0f}KB")
        return output_path
    except Exception as e:
        _fail_job(job_id, f"TTS failed: {e}")
        raise


@celery_app.task(name="transcribe_audio", bind=True)
def task_transcribe_audio(self, audio_path: str, job_id: str) -> dict:
    try:
        _update_job(job_id, "processing", "transcribing", 0.45)
        words = transcribe_with_timestamps(audio_path)
        job_dir = get_job_dir(job_id)
        (job_dir / "words.json").write_text(json.dumps(words, ensure_ascii=False))
        script = json.loads((job_dir / "script.json").read_text())

        if not words:
            raise RuntimeError("Whisper produced no word timestamps")

        logger.info(f"Transcription: {len(words)} words, last word at {words[-1]['end']:.1f}s")
        _update_job(job_id, "processing", "transcribing", 0.5)
        return {"words": words, "script": script, "audio_path": audio_path}
    except Exception as e:
        _fail_job(job_id, f"Transcription failed: {e}")
        raise


@celery_app.task(name="fetch_media", bind=True)
def task_fetch_media(self, data: dict, job_id: str) -> dict:
    try:
        _update_job(job_id, "processing", "media", 0.55)
        script = data["script"]
        job_dir = get_job_dir(job_id)
        media_dir = job_dir / "media"
        media_dir.mkdir(exist_ok=True)

        media_paths = []
        for i, scene in enumerate(script["scenes"]):
            keywords = scene.get("keywords_en", ["nature"])
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
            raise RuntimeError("No media downloaded for any scene")

        logger.info(f"Media: {len(media_paths)}/{len(script['scenes'])} scenes have video")
        _update_job(job_id, "processing", "media", 0.65)
        data["media_paths"] = media_paths
        return data
    except Exception as e:
        _fail_job(job_id, f"Media fetch failed: {e}")
        raise


@celery_app.task(name="compose_video", bind=True)
def task_compose_video(self, data: dict, job_id: str) -> str:
    try:
        _update_job(job_id, "processing", "compositing", 0.7)
        job_dir = get_job_dir(job_id)
        output_path = str(job_dir / "final.mp4")
        compose_short(
            scenes=data["script"]["scenes"],
            media_paths=data["media_paths"],
            audio_path=data["audio_path"],
            words=data["words"],
            output_path=output_path,
        )
        _update_job(job_id, "processing", "compositing", 0.9)
        return output_path
    except Exception as e:
        _fail_job(job_id, f"Compositing failed: {e}")
        raise


@celery_app.task(name="finalize", bind=True)
def task_finalize(self, video_path: str, job_id: str) -> str:
    try:
        _update_job(job_id, "processing", "finalizing", 0.95)
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
                        update(Job).where(Job.id == job_id).values(
                            script=script_data,
                            status="editable",
                            video_url=final_path,
                        )
                    )
                    await session.commit()

            asyncio.run(_save_script())
        except Exception as e:
            logger.warning(f"Could not save script to DB: {e}")

        _update_job(job_id, "completed", None, 1.0)
        return final_path
    except Exception as e:
        _fail_job(job_id, f"Finalize failed: {e}")
        raise


@celery_app.task(name="rerender_video", bind=True)
def task_rerender_video(self, job_id: str) -> str:
    """Re-compose video with current editor state (edited scenes/words)."""
    try:
        _update_job(job_id, "rendering", "compositing", 0.1)
        job_dir = get_job_dir(job_id)

        script_path = job_dir / "script.json"
        if not script_path.exists():
            raise RuntimeError("script.json not found")
        script = json.loads(script_path.read_text())

        words_path = job_dir / "words.json"
        words = json.loads(words_path.read_text()) if words_path.exists() else []

        audio_path = str(job_dir / "narration.wav")
        if not (job_dir / "narration.wav").exists():
            raise RuntimeError("narration.wav not found")

        media_dir = job_dir / "media"
        media_paths = []
        if media_dir.exists():
            media_paths = sorted(
                [str(p) for p in media_dir.glob("scene_*.mp4")],
                key=lambda p: int(str(p).split("scene_")[1].split(".")[0])
            )

        if not media_paths:
            raise RuntimeError("No media files found for re-render")

        _update_job(job_id, "rendering", "compositing", 0.3)

        output_path = str(job_dir / "final_edited.mp4")
        compose_short(
            scenes=script["scenes"],
            media_paths=media_paths,
            audio_path=audio_path,
            words=words,
            output_path=output_path,
        )

        _update_job(job_id, "rendering", "finalizing", 0.9)

        output_dir = get_output_dir()
        final_path = str(output_dir / f"{job_id}.mp4")
        shutil.copy2(output_path, final_path)

        _update_job(job_id, "completed", None, 1.0)
        logger.info(f"Re-render completed for job {job_id}")
        return final_path
    except Exception as e:
        _update_job(job_id, "error", error=str(e))
        logger.error(f"Re-render failed for job {job_id}: {e}")
        raise
