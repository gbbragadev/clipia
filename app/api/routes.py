import json
import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

import redis
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.security import get_owned_job
from app.auth.dependencies import get_current_admin_user, get_current_user
from app.config import settings
from app.errors import ErrorMessages, not_found_error, validate_uuid

limiter = Limiter(key_func=get_remote_address)
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
    WaitlistRequest,
)
from app.observability import record_credit_metric
from app.utils.files import bytes_to_gb, path_size_bytes
from app.utils.locks import get_lock
from app.worker.tasks import dispatch_pipeline

router = APIRouter(tags=["jobs"])
_redis = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


def _ensure_storage_ready() -> None:
    settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(settings.STORAGE_DIR)
    if usage.free < 5 * 1024**3:
        raise HTTPException(status_code=503, detail=ErrorMessages.DISK_FULL)


@router.post(
    "/generate",
    summary="Generate a video",
    description="Starts a new video generation job.",
    responses={200: {"description": "Job queued"}}
)
@limiter.limit(settings.RATE_LIMIT_GENERATE)
async def generate(
    request: Request,
    req: GenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Queue a video generation job."""
    async with get_lock(f"generate:{user.id}"):
        _ensure_storage_ready()
        debit = await db.execute(
            update(User)
            .where(User.id == user.id, User.email_verified.is_(True), User.credits >= 1)
            .values(credits=User.credits - 1)
        )
        if debit.rowcount == 0:
            fresh_user = await db.get(User, user.id)
            if fresh_user is None:
                raise HTTPException(status_code=401, detail=ErrorMessages.UNAUTHORIZED)
            if not fresh_user.email_verified:
                raise HTTPException(status_code=403, detail=ErrorMessages.EMAIL_NOT_VERIFIED)
            raise HTTPException(status_code=402, detail=ErrorMessages.INSUFFICIENT_CREDITS)

        fresh_user = await db.get(User, user.id)
        if fresh_user is None:
            raise HTTPException(status_code=401, detail=ErrorMessages.UNAUTHORIZED)
        record_credit_metric("debit", 1)

        job = Job(
            user_id=fresh_user.id,
            topic=req.topic,
            style=req.style,
            duration_target=req.duration_target,
            template_id=req.template_id,
            status="queued",
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

    job_id = str(job.id)

    _redis.hset(f"job:{job_id}", mapping={
        "status": "queued",
        "progress": "0",
        "current_step": "",
        "error": "",
        "detail": "",
        "template_id": req.template_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    dispatch_pipeline(job_id, req.topic, req.style, req.duration_target, template_id=req.template_id)

    return {"job_id": job_id, "status": "queued"}


@router.get(
    "/jobs/{job_id}",
    summary="Get job status",
    description="Gets current job status.",
    responses={200: {"description": "Job status"}}
)
async def get_job(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve job details."""
    job = await get_owned_job(db, user, job_id)
    job_id = str(job.id)
    data = _redis.hgetall(f"job:{job_id}")
    if not data:
        raise not_found_error()
    return JobStatus(
        job_id=str(job.id),
        status=data.get("status", "unknown"),
        progress=float(data.get("progress", 0)),
        current_step=data.get("current_step") or None,
        error=data.get("error") or None,
        detail=data.get("detail") or None,
        created_at=data.get("created_at", ""),
        download_url=f"/api/v1/jobs/{job_id}/download" if data.get("status") == "completed" else None,
    )


@router.get(
    "/jobs/{job_id}/download",
    summary="Download job",
    description="Downloads generated video.",
    responses={200: {"description": "Video stream"}, 404: {"description": "Not found"}}
)
async def download_job(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve job details."""
    job = await get_owned_job(db, user, job_id)
    file_path = Path(settings.STORAGE_DIR) / "output" / f"{job.id}.mp4"
    if not file_path.exists():
        raise not_found_error()
    return FileResponse(str(file_path), media_type="video/mp4", filename=f"clipia-{str(job.id)[:8]}.mp4")


@router.post(
    "/waitlist",
    status_code=201,
    summary="Join waitlist",
    description="Adds an email to waitlist.",
    responses={201: {"description": "Added to waitlist"}}
)
async def join_waitlist(body: WaitlistRequest, db: AsyncSession = Depends(get_db)):
    """Join waitlist."""
    result = await db.execute(select(WaitlistEntry).where(WaitlistEntry.email == body.email))
    if result.scalar_one_or_none() is not None:
        return {"message": "Email já cadastrado na waitlist"}

    entry = WaitlistEntry(email=body.email)
    db.add(entry)
    await db.commit()
    return {"message": "Adicionado à waitlist com sucesso"}


@router.get(
    "/templates",
    summary="List templates",
    description="Returns available templates.",
    responses={200: {"description": "List of templates"}}
)
async def list_templates():
    """Return available video templates."""
    from app.templates import TEMPLATES
    return [
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "icon": t.icon,
            "layout_type": t.layout.type,
        }
        for t in TEMPLATES.values()
    ]


# ── Editor endpoints ──────────────────────────────────────────


@router.get(
    "/jobs/{job_id}/composition",
    summary="Get composition",
    description="Returns the job's script and media.",
    responses={200: {"description": "Composition data"}}
)
async def get_composition(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return full composition data for the Remotion editor."""
    job = await get_owned_job(db, user, job_id)
    job_id = str(job.id)

    job_dir = Path(settings.STORAGE_DIR) / "jobs" / job_id

    # Load script from filesystem or DB
    script_path = job_dir / "script.json"
    if script_path.exists():
        script = json.loads(script_path.read_text())
    else:
        if not job.script:
            raise not_found_error()
        script = job.script

    # Load word timestamps
    words_path = job_dir / "words.json"
    words = json.loads(words_path.read_text()) if words_path.exists() else []

    # Enumerate media files
    media_dir = job_dir / "media"
    media_urls = []
    if media_dir.exists():
        # Check for local template background first
        bg_file = media_dir / "background.mp4"
        if bg_file.exists():
            media_urls = [f"/storage/jobs/{job_id}/media/background.mp4"]
        else:
            for i in range(len(script.get("scenes", []))):
                scene_file = media_dir / f"scene_{i}.mp4"
                if scene_file.exists():
                    media_urls.append(f"/storage/jobs/{job_id}/media/scene_{i}.mp4")

    audio_url = f"/storage/jobs/{job_id}/narration.wav" if (job_dir / "narration.wav").exists() else ""

    # Load editor state from DB if exists
    editor_state = job.editor_state

    # Get template info
    from app.templates import get_template
    job_template_id = getattr(job, "template_id", "stock_narration")
    tmpl = get_template(job_template_id)

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
        template_id=job_template_id,
        layout_type=tmpl.layout.type,
        pending_credits=job.pending_credits if job else 0.0,
    )


@router.post(
    "/jobs/{job_id}/edit",
    summary="Save edit",
    description="Saves current editor state.",
    responses={200: {"description": "Saved"}}
)
async def save_editor_state(
    request: Request,
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Auto-save editor state."""
    raw_body = await request.body()
    if len(raw_body) > 512_000:
        raise HTTPException(status_code=413, detail=ErrorMessages.PAYLOAD_TOO_LARGE)
    req = EditRequest.model_validate_json(raw_body)

    job = await get_owned_job(db, user, job_id)
    job_id = str(job.id)

    await db.execute(update(Job).where(Job.id == job.id).values(editor_state=req.editor_state))
    await db.commit()

    # Sync edited state to disk for the render pipeline
    try:
        job_dir = Path(settings.STORAGE_DIR) / "jobs" / job_id
        if req.editor_state:
            # Save full editor_state for re-render (music, subtitleStyle, overlays)
            state_path = job_dir / "editor_state.json"
            state_path.write_text(json.dumps(req.editor_state, ensure_ascii=False, indent=2))

            # Sync scenes/words to their own files
            comp = req.editor_state.get("composition", {})
            script_path = job_dir / "script.json"
            if script_path.exists() and comp.get("scenes"):
                script = json.loads(script_path.read_text())
                script["scenes"] = comp["scenes"]
                script_path.write_text(json.dumps(script, ensure_ascii=False, indent=2))
            if comp.get("words"):
                words_path = job_dir / "words.json"
                words_path.write_text(json.dumps(comp["words"], ensure_ascii=False))
    except Exception as e:
        logger.warning(f"Could not sync editor state to disk for {job_id}: {e}")

    return {"status": "saved"}


@router.post(
    "/jobs/{job_id}/regenerate-tts",
    summary="Regenerate TTS",
    description="Regenerates the video narration.",
    responses={200: {"description": "Regenerated"}}
)
async def regenerate_tts(
    job_id: str,
    req: RegenerateTTSRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Regenerate TTS narration with new voice/rate/pitch settings."""
    job = await get_owned_job(db, user, job_id)
    job_id = str(job.id)
    job_dir = Path(settings.STORAGE_DIR) / "jobs" / job_id
    if not job_dir.exists():
        raise not_found_error()

    # Read current script
    script_path = job_dir / "script.json"
    if not script_path.exists():
        raise not_found_error()

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


@router.post(
    "/jobs/{job_id}/ai-suggest",
    summary="AI Suggestions",
    description="Suggests edits using AI.",
    responses={200: {"description": "Suggestions"}}
)
async def ai_suggest(
    job_id: str,
    req: AISuggestRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get AI suggestions for script improvement. Acumula 0.5 credito por chamada."""
    job = await get_owned_job(db, user, job_id)

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

    async with get_lock(f"job:{job.id}:pending_credits"):
        refreshed_job = await db.get(Job, job.id)
        refreshed_job.pending_credits = (refreshed_job.pending_credits or 0.0) + 0.5
        await db.commit()
        pending_credits = refreshed_job.pending_credits

    result["pending_credits"] = pending_credits
    return result


@router.post(
    "/jobs/{job_id}/render",
    summary="Render video",
    description="Starts render job.",
    responses={200: {"description": "Render queued"}}
)
async def render_video(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Re-render video with current editor state via FFmpeg+NVENC."""
    job = await get_owned_job(db, user, job_id)
    job_id = str(job.id)
    async with get_lock(f"render:{job_id}"):
        pending = job.pending_credits or 0.0
        if pending > 0:
            user_result = await db.execute(select(User).where(User.id == user.id))
            fresh_user = user_result.scalar_one()
            if fresh_user.credits < pending:
                raise HTTPException(
                    status_code=402,
                    detail=ErrorMessages.INSUFFICIENT_CREDITS,
                )
            fresh_user.credits = int(fresh_user.credits - pending)
            job.pending_credits = 0.0
            await db.commit()
            record_credit_metric("debit", pending)

    job_dir = Path(settings.STORAGE_DIR) / "jobs" / job_id
    if not job_dir.exists():
        raise not_found_error()

    from app.worker.tasks import task_rerender_video
    task_rerender_video.delay(job_id)

    return {
        "status": "rendering",
        "message": "Re-render iniciado com edicoes atuais.",
    }


@router.post(
    "/jobs/{job_id}/reset",
    summary="Reset job",
    description="Resets job state to defaults.",
    responses={200: {"description": "Reset successfully"}}
)
async def reset_job(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reset job to original state. Costs 1 credit, clears pending_credits."""
    job = await get_owned_job(db, user, job_id)
    async with get_lock(f"reset:{job_id}"):
        fresh_user = await db.get(User, user.id)
        if fresh_user.credits < 1:
            raise HTTPException(status_code=402, detail=ErrorMessages.INSUFFICIENT_CREDITS)

        fresh_user.credits -= 1
        job.pending_credits = 0.0
        job.editor_state = None
        await db.commit()
        record_credit_metric("debit", 1)

        return {"status": "reset", "credits_remaining": fresh_user.credits}


@router.get(
    "/jobs/{job_id}/status",
    summary="Job status",
    description="Gets job status from Redis.",
    responses={200: {"description": "Status"}}
)
async def job_status(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Quick status check from Redis for polling."""
    job = await get_owned_job(db, user, job_id)
    job_id = str(job.id)
    data = _redis.hgetall(f"job:{job_id}")
    if not data:
        raise not_found_error()
    return {
        "status": data.get("status", "unknown"),
        "progress": float(data.get("progress", 0)),
        "current_step": data.get("current_step", ""),
        "error": data.get("error", ""),
        "detail": data.get("detail", ""),
    }


@router.post(
    "/jobs/{job_id}/cancel",
    summary="Cancel job",
    description="Cancels an ongoing job.",
    responses={200: {"description": "Cancel initiated"}}
)
async def cancel_job(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve job details."""
    job = await get_owned_job(db, user, job_id)
    job_id = str(job.id)

    _redis.set(f"job:{job_id}:cancelled", "true")
    _redis.hset(
        f"job:{job_id}",
        mapping={"status": "cancelling", "detail": "Cancelamento solicitado pelo usuario."},
    )
    return {"status": "cancelling"}


@router.get(
    "/jobs",
    summary="List jobs",
    description="List user's jobs.",
    responses={200: {"description": "List of jobs"}}
)
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


@router.get(
    "/admin/storage-stats",
    summary="Storage stats",
    description="Admin storage stats.",
    responses={200: {"description": "Stats"}}
)
async def storage_stats(
    _admin_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    storage_dir = settings.STORAGE_DIR
    jobs_dir = storage_dir / "jobs"
    output_dir = storage_dir / "output"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    result = await db.execute(select(Job.id, Job.created_at, Job.status))
    jobs = result.all()
    job_ids = {str(row.id) for row in jobs}

    orphan_dirs = 0
    if jobs_dir.exists():
        for entry in jobs_dir.iterdir():
            if entry.is_dir() and entry.name not in job_ids:
                orphan_dirs += 1

    total_jobs = len(jobs)
    failed_jobs = sum(1 for row in jobs if row.status == "failed")
    oldest_created = None
    for row in jobs:
        if row.created_at is None:
            continue
        created_at = row.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        else:
            created_at = created_at.astimezone(timezone.utc)
        if oldest_created is None or created_at < oldest_created:
            oldest_created = created_at

    oldest_job_days = 0
    if oldest_created is not None:
        oldest_job_days = max(0, int((datetime.now(timezone.utc) - oldest_created).days))

    return {
        "jobs_dir_size_gb": bytes_to_gb(path_size_bytes(jobs_dir)),
        "output_dir_size_gb": bytes_to_gb(path_size_bytes(output_dir)),
        "total_jobs": total_jobs,
        "failed_jobs": failed_jobs,
        "orphan_dirs": orphan_dirs,
        "oldest_job_days": oldest_job_days,
    }
