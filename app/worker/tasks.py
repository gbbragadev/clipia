import asyncio
import json
import logging
import shutil
from datetime import datetime

import redis

from app.config import settings
from app.services.compositor import compose_short
from app.services.media import download_media, search_videos
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


def dispatch_pipeline(job_id: str, topic: str, style: str, duration_target: int):
    from celery import chain

    _redis.hset(f"job:{job_id}", mapping={
        "status": "queued",
        "current_step": "",
        "progress": "0",
        "error": "",
        "created_at": datetime.utcnow().isoformat(),
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


@celery_app.task(name="generate_script")
def task_generate_script(job_id: str, topic: str, style: str, duration_target: int) -> dict:
    _update_job(job_id, "processing", "scripting", 0.1)
    script = generate_script(topic, style, duration_target)
    job_dir = get_job_dir(job_id)
    (job_dir / "script.json").write_text(json.dumps(script, ensure_ascii=False))
    _update_job(job_id, "processing", "scripting", 0.16)
    return script


@celery_app.task(name="synthesize_audio")
def task_synthesize_audio(script: dict, job_id: str) -> str:
    _update_job(job_id, "processing", "tts", 0.2)
    job_dir = get_job_dir(job_id)
    output_path = str(job_dir / "narration.wav")
    synthesize_narration(
        text=script["narration"],
        output_path=output_path,
        speaker_wav=str(settings.REFERENCE_VOICE),
    )
    _update_job(job_id, "processing", "tts", 0.4)
    return output_path


@celery_app.task(name="transcribe_audio")
def task_transcribe_audio(audio_path: str, job_id: str) -> dict:
    _update_job(job_id, "processing", "transcribing", 0.45)
    words = transcribe_with_timestamps(audio_path)
    job_dir = get_job_dir(job_id)
    (job_dir / "words.json").write_text(json.dumps(words, ensure_ascii=False))
    script = json.loads((job_dir / "script.json").read_text())
    _update_job(job_id, "processing", "transcribing", 0.5)
    return {"words": words, "script": script, "audio_path": audio_path}


@celery_app.task(name="fetch_media")
def task_fetch_media(data: dict, job_id: str) -> dict:
    _update_job(job_id, "processing", "media", 0.55)
    script = data["script"]
    job_dir = get_job_dir(job_id)
    media_dir = job_dir / "media"
    media_dir.mkdir(exist_ok=True)

    media_paths = []
    for i, scene in enumerate(script["scenes"]):
        query = " ".join(scene["keywords_en"][:3])
        results = asyncio.run(search_videos(query, per_page=3))
        if results:
            dest = str(media_dir / f"scene_{i}.mp4")
            asyncio.run(download_media(results[0]["url"], dest))
            media_paths.append(dest)

    _update_job(job_id, "processing", "media", 0.65)
    data["media_paths"] = media_paths
    return data


@celery_app.task(name="compose_video")
def task_compose_video(data: dict, job_id: str) -> str:
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


@celery_app.task(name="finalize")
def task_finalize(video_path: str, job_id: str) -> str:
    _update_job(job_id, "processing", "finalizing", 0.95)
    output_dir = get_output_dir()
    final_path = str(output_dir / f"{job_id}.mp4")
    shutil.copy2(video_path, final_path)
    cleanup_job_dir(job_id)
    _update_job(job_id, "completed", None, 1.0)
    return final_path
