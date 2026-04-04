import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

import redis
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.config import settings
from app.db.engine import get_db
from app.db.models import Job, User, WaitlistEntry
from app.models import (
    AISuggestRequest,
    CompositionResponse,
    EditRequest,
    GenerateRequest,
    JobStatus,
    RegenerateMediaRequest,
    RegenerateTTSRequest,
)
from app.worker.tasks import dispatch_pipeline

router = APIRouter()
_redis = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


@router.post("/generate")
async def generate(
    req: GenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.credits < 1:
        raise HTTPException(status_code=402, detail="Créditos insuficientes")

    job = Job(
        user_id=user.id,
        topic=req.topic,
        style=req.style,
        duration_target=req.duration_target,
        status="queued",
    )
    db.add(job)
    user.credits -= 1
    await db.commit()
    await db.refresh(job)

    job_id = str(job.id)

    _redis.hset(f"job:{job_id}", mapping={
        "status": "queued",
        "progress": "0",
        "current_step": "",
        "error": "",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    dispatch_pipeline(job_id, req.topic, req.style, req.duration_target)

    return {"job_id": job_id, "status": "queued"}


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    data = _redis.hgetall(f"job:{job_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatus(
        job_id=job_id,
        status=data.get("status", "unknown"),
        progress=float(data.get("progress", 0)),
        current_step=data.get("current_step") or None,
        error=data.get("error") or None,
        created_at=data.get("created_at", ""),
        download_url=f"/api/v1/jobs/{job_id}/download" if data.get("status") == "completed" else None,
    )


@router.get("/jobs/{job_id}/download")
def download_job(job_id: str):
    file_path = Path(settings.STORAGE_DIR) / "output" / f"{job_id}.mp4"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Video not found")
    return FileResponse(str(file_path), media_type="video/mp4", filename=f"clipia-{job_id[:8]}.mp4")


class WaitlistRequest(BaseModel):
    email: str


@router.post("/waitlist", status_code=201)
async def join_waitlist(body: WaitlistRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WaitlistEntry).where(WaitlistEntry.email == body.email))
    if result.scalar_one_or_none() is not None:
        return {"message": "Email já cadastrado na waitlist"}

    entry = WaitlistEntry(email=body.email)
    db.add(entry)
    await db.commit()
    return {"message": "Adicionado à waitlist com sucesso"}


# ── Editor endpoints ──────────────────────────────────────────


@router.get("/jobs/{job_id}/composition")
async def get_composition(job_id: str, db: AsyncSession = Depends(get_db)):
    """Return full composition data for the Remotion editor."""
    job_dir = Path(settings.STORAGE_DIR) / "jobs" / job_id

    # Load script from filesystem or DB
    script_path = job_dir / "script.json"
    if script_path.exists():
        script = json.loads(script_path.read_text())
    else:
        result = await db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()
        if not job or not job.script:
            raise HTTPException(status_code=404, detail="Composition not found")
        script = job.script

    # Load word timestamps
    words_path = job_dir / "words.json"
    words = json.loads(words_path.read_text()) if words_path.exists() else []

    # Enumerate media files
    media_dir = job_dir / "media"
    media_urls = []
    if media_dir.exists():
        for i in range(len(script.get("scenes", []))):
            scene_file = media_dir / f"scene_{i}.mp4"
            if scene_file.exists():
                media_urls.append(f"/storage/jobs/{job_id}/media/scene_{i}.mp4")

    audio_url = f"/storage/jobs/{job_id}/narration.wav" if (job_dir / "narration.wav").exists() else ""

    # Load editor state from DB if exists
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    editor_state = job.editor_state if job else None

    return CompositionResponse(
        job_id=job_id,
        script=script,
        words=words,
        audio_url=audio_url,
        media_urls=media_urls,
        subtitle_style={
            "fontFamily": "Montserrat, sans-serif",
            "fontSize": 52,
            "color": "#FFFFFF",
            "outlineColor": "#000000",
            "backgroundColor": "rgba(0, 0, 0, 0.6)",
            "position": "bottom",
            "marginBottom": 180,
            "maxWordsPerChunk": 3,
        },
        editor_state=editor_state,
    )


@router.post("/jobs/{job_id}/edit")
async def save_editor_state(
    job_id: str,
    req: EditRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Auto-save editor state."""
    result = await db.execute(select(Job).where(Job.id == job_id, Job.user_id == user.id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    await db.execute(update(Job).where(Job.id == job_id).values(editor_state=req.editor_state))
    await db.commit()
    return {"status": "saved"}


@router.post("/jobs/{job_id}/regenerate-tts")
async def regenerate_tts(
    job_id: str,
    req: RegenerateTTSRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Regenerate TTS narration with new voice/rate/pitch settings."""
    job_dir = Path(settings.STORAGE_DIR) / "jobs" / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail="Job not found")

    # Read current script
    script_path = job_dir / "script.json"
    if not script_path.exists():
        raise HTTPException(status_code=404, detail="Script not found")

    script = json.loads(script_path.read_text())
    narration = req.text if req.text else script.get("narration", "")

    # Regenerate TTS (async to avoid blocking the event loop)
    audio_path = str(job_dir / "narration.wav")
    from app.services.tts import synthesize_narration_async
    await synthesize_narration_async(
        text=narration,
        output_path=audio_path,
        voice_id=req.voice_id or "pt-BR-AntonioNeural",
        rate=req.rate if req.rate is not None else -10,
        pitch=req.pitch if req.pitch is not None else 5,
    )

    # Re-transcribe with Whisper (keep old words as fallback)
    words_path = job_dir / "words.json"
    old_words = json.loads(words_path.read_text()) if words_path.exists() else []
    words = []
    try:
        from app.services.transcriber import transcribe_with_timestamps
        words = transcribe_with_timestamps(audio_path)
    except Exception as e:
        logger.warning(f"Whisper transcription failed, keeping old timestamps: {e}")
        words = old_words

    # Save updated words
    if words:
        words_path.write_text(json.dumps(words, ensure_ascii=False))

    return {
        "audio_url": f"/storage/jobs/{job_id}/narration.wav",
        "words": words,
    }


@router.post("/jobs/{job_id}/ai-suggest")
async def ai_suggest(
    job_id: str,
    req: AISuggestRequest,
    user: User = Depends(get_current_user),
):
    """Get AI suggestions for script improvement."""
    import anthropic

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    script_json = json.dumps(req.context, ensure_ascii=False, indent=2) if req.context else "{}"

    message = client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=1500,
        messages=[{
            "role": "user",
            "content": f"""Voce e um editor de video especialista em conteudo viral para TikTok, Reels e Shorts.

Roteiro atual do video:
{script_json}

Pedido do criador: {req.message}

Responda APENAS em JSON valido com sugestoes especificas:
{{
  "suggestions": [
    {{
      "type": "rewrite_scene",
      "scene_index": 0,
      "new_text": "texto melhorado da cena",
      "reason": "por que esta versao e melhor"
    }}
  ],
  "general_feedback": "feedback geral sobre o roteiro"
}}

Regras:
- Mantenha o tom conversacional e natural em portugues brasileiro
- Cada sugestao deve ter um scene_index valido (0-based)
- O new_text deve ter duracao similar ao original
- Seja especifico no reason (nao generico)
- Maximo 3 sugestoes por resposta""",
        }],
    )

    raw = message.content[0].text
    # Try to parse JSON, handling potential markdown code blocks
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {"suggestions": [], "general_feedback": raw}

    return result


@router.post("/jobs/{job_id}/render")
async def render_video(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Re-render video with current editor state via FFmpeg+NVENC."""
    result = await db.execute(select(Job).where(Job.id == job_id, Job.user_id == user.id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Dispatch render task (reuses existing compose pipeline)
    job_dir = Path(settings.STORAGE_DIR) / "jobs" / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail="Job files not found")

    # For now, just copy the existing final.mp4 to output
    # Full re-render with editor state would need a new Celery task
    final_path = job_dir / "final.mp4"
    if not final_path.exists():
        raise HTTPException(status_code=404, detail="Video not rendered yet")

    import shutil
    output_dir = Path(settings.STORAGE_DIR) / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{job_id}.mp4"
    shutil.copy2(str(final_path), str(output_path))

    return {
        "status": "completed",
        "download_url": f"/api/v1/jobs/{job_id}/download",
    }


@router.get("/jobs")
async def list_jobs(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all jobs for the current user, with real-time status from Redis."""
    result = await db.execute(
        select(Job).where(Job.user_id == user.id).order_by(Job.created_at.desc()).limit(50)
    )
    jobs = result.scalars().all()
    items = []
    for j in jobs:
        # Redis has the real-time status; DB may be stale
        redis_data = _redis.hgetall(f"job:{j.id}")
        status = redis_data.get("status", j.status) if redis_data else j.status
        has_video = j.video_url or (Path(settings.STORAGE_DIR) / "output" / f"{j.id}.mp4").exists()
        # Treat completed jobs as editable if they have composition files
        if status == "completed":
            job_dir = Path(settings.STORAGE_DIR) / "jobs" / str(j.id)
            if (job_dir / "script.json").exists():
                status = "editable"
        items.append({
            "job_id": str(j.id),
            "topic": j.topic,
            "style": j.style,
            "status": status,
            "duration_target": j.duration_target,
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "download_url": f"/api/v1/jobs/{j.id}/download" if has_video else None,
        })
    return items
