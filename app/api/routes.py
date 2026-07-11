import asyncio
import json
import logging
import math
import shutil
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from slowapi import Limiter
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.security import get_owned_job
from app.auth.dependencies import get_current_admin_user, get_current_user
from app.config import settings
from app.db.engine import get_db
from app.db.models import CreditAdjustment, CreditPurchase, Feedback, Job, User, VoiceClone, WaitlistEntry
from app.errors import ErrorMessages, not_found_error, validate_uuid
from app.models import (
    AdminCreditAdjustRequest,
    AISuggestRequest,
    CompositionResponse,
    EditRequest,
    FeedbackRequest,
    GenerateRequest,
    JobStatus,
    RegenerateTTSRequest,
    ScriptRefineRequest,
    VoiceDesignRequest,
    WaitlistRequest,
)
from app.observability import record_credit_metric
from app.pricing import get_generation_credit_cost
from app.redis_pool import get_redis
from app.services.llm import complete_text, strip_code_fences
from app.services.remotion import scene_sort_key
from app.services.trends import fetch_trends, get_example_topics
from app.templates import get_template
from app.utils.files import bytes_to_gb, get_job_dir, path_size_bytes
from app.utils.locks import get_lock
from app.utils.media_url import sign_media_url
from app.utils.ratelimit import client_ip
from app.worker.tasks import dispatch_pipeline

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=client_ip)
router = APIRouter(tags=["jobs"])
_redis = get_redis()

_ADMIN_DASHBOARD_RANGES = {"7d": 7, "30d": 30, "90d": 90}

_ALLOWED_AUDIO_MIMES: dict[str, str] = {
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
}


def _validate_audio_upload(content_type: str | None, filename: str | None, size: int, max_mb: int = 50) -> str:
    """Validate audio upload. Returns safe extension. Raises ValueError on failure."""
    if size > max_mb * 1024 * 1024:
        raise ValueError(f"Arquivo muito grande (max {max_mb}MB)")
    ct = (content_type or "").lower().split(";")[0].strip()
    if ct not in _ALLOWED_AUDIO_MIMES:
        raise ValueError(f"Tipo de audio nao suportado: {ct}. Envie WAV, MP3, WebM ou OGG.")
    return _ALLOWED_AUDIO_MIMES[ct]


def _coerce_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _bucket_key(dt: datetime | None) -> str | None:
    utc_dt = _coerce_utc(dt)
    return utc_dt.date().isoformat() if utc_dt else None


def _round2(value: float) -> float:
    return round(value, 2)


async def _build_storage_stats(db: AsyncSession) -> dict[str, int | float]:
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
        created_at = _coerce_utc(row.created_at)
        if created_at is None:
            continue
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


def _empty_daily_series(days: int, now: datetime) -> dict[str, float]:
    series: dict[str, float] = {}
    for offset in range(days):
        day = (now.date()).fromordinal(now.date().toordinal() - (days - 1 - offset))
        series[day.isoformat()] = 0.0
    return series


def _ensure_storage_ready() -> None:
    settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(settings.STORAGE_DIR)
    if usage.free < 5 * 1024**3:
        raise HTTPException(status_code=503, detail=ErrorMessages.DISK_FULL)


async def _debit_credits(db: AsyncSession, user_id, cost: int) -> None:
    """Debito atomico de creditos (mesmo padrao da rota /generate).

    Faz UPDATE ... WHERE credits >= cost (sem read-modify-write) para evitar race/saldo negativo.
    Levanta 402 se nao houver saldo, 403 se o email nao estiver verificado. No-op se cost <= 0.
    """
    if cost <= 0:
        return
    result = await db.execute(
        update(User)
        .where(User.id == user_id, User.email_verified.is_(True), User.credits >= cost)
        .values(credits=User.credits - cost)
    )
    if result.rowcount == 0:
        fresh = await db.get(User, user_id)
        if fresh is None:
            raise HTTPException(status_code=401, detail=ErrorMessages.UNAUTHORIZED)
        if not fresh.email_verified:
            raise HTTPException(status_code=403, detail=ErrorMessages.EMAIL_NOT_VERIFIED)
        raise HTTPException(status_code=402, detail=ErrorMessages.INSUFFICIENT_CREDITS)
    await db.commit()
    record_credit_metric("debit", cost)


async def _refund_credits(db: AsyncSession, user_id, cost: int) -> None:
    """Devolve creditos quando uma operacao paga falha depois do debito. No-op se cost <= 0."""
    if cost <= 0:
        return
    await db.execute(update(User).where(User.id == user_id).values(credits=User.credits + cost))
    await db.commit()
    record_credit_metric("credit", cost)


@router.post(
    "/generate",
    summary="Generate a video",
    description="Starts a new video generation job.",
    responses={200: {"description": "Job queued"}},
)
@limiter.limit(settings.RATE_LIMIT_GENERATE)
async def generate(
    request: Request,
    req: GenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Queue a video generation job."""
    # Dialogo usa 2 vozes ElevenLabs na sintese: o custo e SEMPRE o pricing elevenlabs,
    # decidido aqui (server-side) — nunca por campo de custo vindo do cliente.
    cost_provider = "elevenlabs" if req.narration_mode == "dialogue" else req.voice_provider
    credit_cost = get_generation_credit_cost(req.template_id, cost_provider)

    # Refinos de roteiro (0,5 cada) acumulados em Redis pelo /script-preview/refine:
    # cobra a parte INTEIRA junto da geracao e carrega o resto (2 refinos = 1 credito;
    # 1 refino sozinho fica anotado p/ a proxima — nunca cobra a mais).
    refine_key = f"script_refine_pending:{user.id}"
    try:
        refine_owed = float(_redis.get(refine_key) or 0.0)
    except (TypeError, ValueError):
        refine_owed = 0.0
    refine_extra = int(refine_owed)
    credit_cost += refine_extra

    # Guardrail $: video IA (Seedance) e a operacao mais cara. Teto DIARIO por usuario, vale ate p/
    # conta admin/seed (foi o vetor do gasto de ~$6). O lock por usuario serializa get->incr (sem race).
    is_ai_video = get_template(req.template_id).media.source == "ai_video"
    cap_key = (
        f"aivideo_count:{user.id}:{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
        if is_ai_video and settings.MAX_AI_VIDEO_PER_DAY > 0
        else None
    )

    async with get_lock(f"generate:{user.id}"):
        _ensure_storage_ready()
        if cap_key and int(_redis.get(cap_key) or 0) >= settings.MAX_AI_VIDEO_PER_DAY:
            raise HTTPException(
                status_code=429,
                detail=f"Limite diário de vídeos IA atingido ({settings.MAX_AI_VIDEO_PER_DAY}/dia). Tente novamente amanhã.",
            )
        debit = await db.execute(
            update(User)
            .where(User.id == user.id, User.email_verified.is_(True), User.credits >= credit_cost)
            .values(credits=User.credits - credit_cost)
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
        record_credit_metric("debit", credit_cost)

        # Debito ok: liquida a parte inteira dos refinos e carrega o resto (ex.: 0,5)
        if refine_extra > 0:
            remainder = round(refine_owed - refine_extra, 2)
            if remainder > 0:
                _redis.set(refine_key, str(remainder), ex=86400)
            else:
                _redis.delete(refine_key)

        job = Job(
            user_id=fresh_user.id,
            topic=req.topic,
            style=req.style,
            duration_target=req.duration_target,
            template_id=req.template_id,
            voice_provider=req.voice_provider,
            voice_config=req.voice_config,
            credit_cost=credit_cost,
            status="queued",
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        if cap_key:  # conta a geracao de video IA do dia (so apos debito + job criados com sucesso)
            _redis.incr(cap_key)
            _redis.expire(cap_key, 90000)  # ~25h: zera no dia seguinte

    job_id = str(job.id)

    job_meta = {
        "status": "queued",
        "progress": "0",
        "current_step": "",
        "error": "",
        "detail": "",
        "template_id": req.template_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if req.sfx_enabled is not None:
        job_meta["sfx_enabled"] = "1" if req.sfx_enabled else "0"
    if req.music_enabled is not None:
        job_meta["music_enabled"] = "1" if req.music_enabled else "0"
    if req.narration_mode != "single":
        job_meta["narration_mode"] = req.narration_mode
    _redis.hset(f"job:{job_id}", mapping=job_meta)

    # Roteiro pronto (preview editado): grava script.json ANTES do dispatch — a task
    # generate_script detecta o arquivo e pula a chamada de LLM (1o rascunho incluso).
    if req.custom_script is not None:
        script_path = get_job_dir(job_id) / "script.json"
        script_path.write_text(json.dumps(req.custom_script, ensure_ascii=False, indent=2), encoding="utf-8")
        _redis.hset(f"job:{job_id}", mapping={"custom_script": "1"})

    try:
        dispatch_pipeline(
            job_id,
            req.topic,
            req.style,
            req.duration_target,
            template_id=req.template_id,
            voice_provider=req.voice_provider,
            voice_config=req.voice_config,
            trend_context=req.trend_context,
            narration_mode=req.narration_mode,
        )
    except Exception as e:  # noqa: BLE001 — enfileirar falhou (Celery/Redis down): estorna p/ nao cobrar sem gerar
        await _refund_credits(db, user.id, credit_cost)
        if cap_key:
            _redis.decr(cap_key)  # devolve a cota diaria de ai_video consumida na linha ~243
        _redis.hset(
            f"job:{job_id}",
            mapping={"status": "failed", "error": "Falha ao enfileirar a geracao. Credito estornado."},
        )
        logger.error("dispatch_pipeline falhou job=%s user=%s: %s — credito estornado", job_id, user.id, e)
        raise HTTPException(
            status_code=503,
            detail="Nao foi possivel iniciar a geracao agora. Seu credito foi estornado, tente novamente em instantes.",
        )

    if is_ai_video:
        # Telemetria de custo p/ medir gasto real (dono pediu): Seedance ~R$0,67/s.
        logger.warning(
            "ai_video enfileirado: ~R$%.2f de API estimado (%ds @ R$0,67/s) user=%s job=%s",
            req.duration_target * 0.67,
            req.duration_target,
            user.id,
            job_id,
        )
    return {"job_id": job_id, "status": "queued", "credit_cost": credit_cost}


# ── Rascunho de roteiro (preview gratis + refino 0,5) ────────────────────────

_SCRIPT_PREVIEW_HOURLY_CAP = 10


def _script_preview_rate_limit(user_id) -> None:
    """Cap horario compartilhado preview+refino (anti-farming de LLM)."""
    key = f"script_preview_rl:{user_id}:{datetime.now(timezone.utc).strftime('%Y%m%d%H')}"
    count = _redis.incr(key)
    _redis.expire(key, 3900)
    if int(count) > _SCRIPT_PREVIEW_HOURLY_CAP:
        raise HTTPException(
            status_code=429,
            detail=f"Limite de {_SCRIPT_PREVIEW_HOURLY_CAP} rascunhos/refinos por hora atingido. Tente mais tarde.",
        )


@router.post(
    "/script-preview",
    summary="Rascunho do roteiro (grátis)",
    description="Gera o roteiro ANTES do vídeo para revisar/editar. O 1º rascunho é incluso no custo da geração.",
    responses={200: {"description": "Roteiro gerado"}},
)
async def script_preview(
    req: GenerateRequest,
    user: User = Depends(get_current_user),
):
    """Preview do roteiro sem debitar (incluso). Anti-farming: exige saldo suficiente
    para gerar o video deste template + cap horario."""
    cost_provider = "elevenlabs" if req.narration_mode == "dialogue" else req.voice_provider
    template_cost = get_generation_credit_cost(req.template_id, cost_provider)
    if user.credits < template_cost:
        raise HTTPException(status_code=402, detail=ErrorMessages.INSUFFICIENT_CREDITS)
    _script_preview_rate_limit(user.id)

    from app.services.scriptwriter import generate_script

    try:
        # LLM sync: thread p/ nao bloquear o event loop (gotcha do 502)
        script = await asyncio.to_thread(
            generate_script,
            req.topic,
            req.style,
            req.duration_target,
            req.template_id,
            req.trend_context,
            req.narration_mode == "dialogue",
        )
    except Exception as e:  # noqa: BLE001 — preview nunca cobra; erro vira 502 legivel
        logger.warning("script-preview falhou user=%s: %s", user.id, e)
        raise HTTPException(status_code=502, detail="Não foi possível gerar o rascunho agora. Tente novamente.")

    refine_owed = float(_redis.get(f"script_refine_pending:{user.id}") or 0.0)
    return {"script": script, "refine_cost": 0.5, "refine_pending": refine_owed}


@router.post(
    "/script-preview/refine",
    summary="Refinar o rascunho (0,5 crédito)",
    description="Melhora o roteiro conforme a instrução. Custa 0,5 crédito, somado ao custo da próxima geração.",
    responses={200: {"description": "Roteiro refinado"}},
)
async def script_preview_refine(
    req: ScriptRefineRequest,
    user: User = Depends(get_current_user),
):
    """Refino = 0,5 credito ACUMULADO server-side (Redis) e liquidado no proximo
    /generate (parte inteira; o resto carrega). Nunca um campo de custo do cliente."""
    _script_preview_rate_limit(user.id)

    from app.services.scriptwriter import refine_script

    try:
        refined = await asyncio.to_thread(
            refine_script, req.script, req.instruction, req.duration_target, req.template_id
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("script-refine falhou user=%s: %s", user.id, e)
        raise HTTPException(status_code=502, detail="Não foi possível refinar o rascunho agora. Tente novamente.")

    # Debita os 0,5 SOMENTE com refino entregue
    refine_key = f"script_refine_pending:{user.id}"
    pending = float(_redis.get(refine_key) or 0.0) + 0.5
    _redis.set(refine_key, str(pending), ex=86400)
    return {"script": refined, "refine_cost": 0.5, "refine_pending": pending}


@router.post(
    "/voices/design",
    summary="Design a voice",
    description="Cria uma voz ElevenLabs a partir de uma descrição textual (Voice Design).",
)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def design_voice(
    request: Request,
    req: VoiceDesignRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cria uma voz sob medida a partir de uma descrição. Cobra CREDIT_COST_VOICE_DESIGN creditos."""
    from app.services.elevenlabs_provider import ElevenLabsProvider

    cost = settings.CREDIT_COST_VOICE_DESIGN
    await _debit_credits(db, user.id, cost)
    try:
        voice_id = await ElevenLabsProvider().design_voice(req.name, req.description, req.text)
    except Exception as e:  # noqa: BLE001
        await _refund_credits(db, user.id, cost)
        logger.warning("Voice Design falhou: %s", e)
        raise HTTPException(status_code=502, detail=f"Não foi possível criar a voz: {e}")
    return {"voice_id": voice_id, "name": req.name}


@router.get(
    "/trends",
    summary="Trending topics",
    description="Temas em alta de fontes gratuitas (Reddit, Hacker News, Google Trends BR).",
)
async def get_trends(
    nicho: str | None = None,
    user: User = Depends(get_current_user),
):
    """Temas em alta para o painel 'Em alta'. Nunca 500 por falha de fonte externa."""
    try:
        trends = await fetch_trends(niche=nicho)
    except Exception as e:  # noqa: BLE001 — descoberta e best-effort
        logger.warning("fetch_trends falhou para nicho=%s: %s", nicho, e)
        trends = []
    return {"trends": trends}


@router.get(
    "/example-topics/{nicho}",
    summary="Temas prontos do nicho",
    description="8 temas prontos pt-BR gerados por IA, renovados a cada hora (cache).",
    responses={200: {"description": "Lista de temas"}},
)
async def example_topics(
    nicho: str,
    user: User = Depends(get_current_user),
):
    """Temas rotativos por IA (cache 1h). Lista vazia em falha — o frontend usa o
    fallback estático de niches.ts, então o painel NUNCA fica sem sugestão.
    Autenticado: evita farming de LLM por anônimos."""
    try:
        topics = await get_example_topics(nicho)
    except Exception as e:  # noqa: BLE001 — sugestões são best-effort
        logger.warning("example_topics falhou para nicho=%s: %s", nicho, e)
        topics = []
    return {"topics": topics}


@router.get(
    "/jobs/{job_id}",
    summary="Get job status",
    description="Gets current job status.",
    responses={200: {"description": "Job status"}},
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
    responses={200: {"description": "Video stream"}, 404: {"description": "Not found"}},
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


@router.get(
    "/jobs/{job_id}/thumbnail",
    summary="Job thumbnail",
    description="Poster JPEG do video final (frame extraido no finalize).",
    responses={200: {"description": "JPEG"}, 404: {"description": "Not found"}},
)
async def job_thumbnail(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await get_owned_job(db, user, job_id)
    file_path = Path(settings.STORAGE_DIR) / "output" / f"{job.id}.jpg"
    if not file_path.exists():
        raise not_found_error()
    return FileResponse(str(file_path), media_type="image/jpeg")


@router.get(
    "/config",
    summary="Public config",
    description="Valores de oferta exibidos no frontend (nunca hardcodar copy de oferta).",
    responses={200: {"description": "Config"}},
)
async def public_config():
    """Fonte única dos números prometidos na UI (guardrail de confiança do DESIGN.md)."""
    return {
        "welcome_credit_bonus": settings.WELCOME_CREDIT_BONUS,
        "purchase_bonus_percent": settings.PURCHASE_BONUS_PERCENT,
    }


@router.post(
    "/waitlist",
    status_code=201,
    summary="Join waitlist",
    description="Adds an email to waitlist.",
    responses={201: {"description": "Added to waitlist"}},
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
    responses={200: {"description": "List of templates"}},
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
            "media_source": t.media.source,
            "default_voice_provider": t.voice.provider,
            "default_voice_id": t.voice.voice_id,
            # Aceita o modo dialogo (2 vozes)? dialogue_duo ja E dialogo nativo -> False (sem toggle).
            "dialogue_capable": t.dialogue_capable,
            "credit_costs": {
                "edge": get_generation_credit_cost(t.id, "edge"),
                "elevenlabs": get_generation_credit_cost(t.id, "elevenlabs"),
                "custom": get_generation_credit_cost(t.id, "custom"),
            },
        }
        for t in TEMPLATES.values()
    ]


# ── Voice endpoints ───────────────────────────────────────────


@router.get(
    "/voices",
    summary="List voices",
    description="Returns available voices across all providers.",
    responses={200: {"description": "List of voices"}},
)
async def list_voices(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all available voices (Edge + ElevenLabs + user clones)."""
    from app.services.edge_provider import EDGE_VOICES

    voices = [v.__dict__ for v in EDGE_VOICES]

    # ElevenLabs voices (if API key configured)
    if settings.ELEVENLABS_API_KEY:
        try:
            from app.services.elevenlabs_provider import ElevenLabsProvider

            provider = ElevenLabsProvider()
            el_voices = await provider.list_voices()
            voices.extend(v.__dict__ for v in el_voices)
        except Exception as e:
            logger.warning(f"Failed to fetch ElevenLabs voices: {e}")

    # User's cloned voices from DB
    result = await db.execute(select(VoiceClone).where(VoiceClone.user_id == user.id))
    clones = result.scalars().all()
    for clone in clones:
        voices.append(
            {
                "id": clone.external_voice_id,
                "name": f"{clone.name} (clone)",
                "provider": clone.provider,
                "language": "multilingual",
                "is_clone": True,
                "clone_id": str(clone.id),
            }
        )

    return voices


@router.post(
    "/voices/clone",
    summary="Clone voice",
    description="Clone a voice using ElevenLabs Instant Voice Cloning.",
    responses={200: {"description": "Voice cloned"}},
)
@limiter.limit("3/hour")
async def clone_voice(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Clone a voice from uploaded audio samples.

    Recebe ``multipart/form-data`` com:
      - ``files``: 1+ arquivos de audio (WAV/MP3/WebM/OGG, max 10MB cada)
      - ``name``: nome da voz (1-100 chars)
      - ``description``: descricao opcional (max 500 chars)

    Nota: ``name``/``description`` vem do proprio form multipart (NAO de um body
    JSON do Pydantic) — misturar ``VoiceCloneRequest`` (body JSON) com
    ``request.form()`` (multipart) e impossivel em HTTP real (422). Os testes
    chamam ``.__wrapped__`` passando os argumentos explicitamente, por isso o
    bug so aparecia em producao.
    """
    if not settings.ELEVENLABS_API_KEY:
        raise HTTPException(status_code=503, detail="Voice cloning not available")

    # Check max clones per user (limit 5)
    result = await db.execute(select(VoiceClone).where(VoiceClone.user_id == user.id))
    if len(result.scalars().all()) >= 5:
        raise HTTPException(status_code=400, detail="Máximo de 5 vozes clonadas por usuário")

    # Get uploaded files + metadata from multipart
    form = await request.form()
    files = form.getlist("files")
    if not files:
        raise HTTPException(status_code=400, detail="Envie pelo menos 1 arquivo de áudio")

    name = (form.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Informe um nome para a voz")
    if len(name) > 100:
        raise HTTPException(status_code=400, detail="Nome muito longo (max 100 caracteres)")
    description = (form.get("description") or "").strip()
    if len(description) > 500:
        raise HTTPException(status_code=400, detail="Descrição muito longa (max 500 caracteres)")

    audio_bytes = []
    for f in files:
        content = await f.read()
        try:
            _validate_audio_upload(content_type=f.content_type, filename=f.filename, size=len(content), max_mb=10)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        audio_bytes.append(content)

    from app.services.elevenlabs_provider import ElevenLabsProvider

    cost = settings.CREDIT_COST_VOICE_CLONE
    await _debit_credits(db, user.id, cost)
    provider = ElevenLabsProvider()
    try:
        voice_id = await provider.clone_voice(name, audio_bytes, description)
    except Exception as e:  # noqa: BLE001
        await _refund_credits(db, user.id, cost)
        logger.warning("Voice clone falhou: %s", e)
        raise HTTPException(status_code=502, detail=f"Não foi possível clonar a voz: {e}")

    clone = VoiceClone(
        user_id=user.id,
        name=name,
        provider="elevenlabs",
        external_voice_id=voice_id,
        samples_count=len(audio_bytes),
    )
    db.add(clone)
    await db.commit()
    await db.refresh(clone)

    return {
        "clone_id": str(clone.id),
        "voice_id": voice_id,
        "name": name,
    }


@router.delete(
    "/voices/{clone_id}",
    summary="Delete cloned voice",
    description="Deletes a user's cloned voice.",
    responses={200: {"description": "Voice deleted"}},
)
async def delete_voice(
    clone_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a cloned voice."""
    validate_uuid(clone_id)
    result = await db.execute(select(VoiceClone).where(VoiceClone.id == clone_id, VoiceClone.user_id == user.id))
    clone = result.scalar_one_or_none()
    if clone is None:
        raise not_found_error()

    # Delete from ElevenLabs
    if clone.provider == "elevenlabs" and settings.ELEVENLABS_API_KEY:
        try:
            from app.services.elevenlabs_provider import ElevenLabsProvider

            provider = ElevenLabsProvider()
            await provider.delete_voice(clone.external_voice_id)
        except Exception as e:
            logger.warning(f"Failed to delete voice from ElevenLabs: {e}")

    await db.delete(clone)
    await db.commit()
    return {"status": "deleted"}


@router.post(
    "/jobs/{job_id}/upload-audio",
    summary="Upload custom audio",
    description="Upload a custom audio file for a job.",
    responses={200: {"description": "Audio uploaded"}},
)
@limiter.limit("10/minute")
async def upload_audio(
    request: Request,
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload custom audio (WAV/MP3/WebM) for a job."""
    job = await get_owned_job(db, user, job_id)
    job_id = str(job.id)

    form = await request.form()
    file = form.get("file")
    if file is None:
        raise HTTPException(status_code=400, detail="Envie um arquivo de áudio")

    content = await file.read()
    try:
        ext = _validate_audio_upload(content_type=file.content_type, filename=file.filename, size=len(content))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    job_dir = Path(settings.STORAGE_DIR) / "jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # Save uploaded file
    upload_path = str(job_dir / f"upload{ext}")
    with open(upload_path, "wb") as f:
        f.write(content)

    # Validate
    from app.services.custom_audio_provider import validate_audio_file

    try:
        meta = validate_audio_file(upload_path)
    except ValueError as e:
        Path(upload_path).unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(e))

    # Normalize to WAV
    output_path = str(job_dir / "narration.wav")
    from app.services.custom_audio_provider import normalize_audio

    await asyncio.to_thread(normalize_audio, upload_path, output_path)

    # Transcribe with Whisper for word timestamps
    words = []
    try:
        from app.services.transcriber import transcribe_with_timestamps

        # to_thread: normalize_audio (ffmpeg) e transcribe (Whisper/Groq) sao sincronos e bloqueiam o
        # event loop. Em thread separada o backend continua respondendo durante a transcricao.
        words = await asyncio.to_thread(transcribe_with_timestamps, output_path)
        (job_dir / "words.json").write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.warning(f"Whisper transcription of uploaded audio failed: {e}")

    return {
        "audio_url": sign_media_url(f"/storage/jobs/{job_id}/narration.wav"),
        "words": words,
        "duration": meta["duration"],
    }


# ── Editor endpoints ──────────────────────────────────────────


@router.get(
    "/jobs/{job_id}/composition",
    summary="Get composition",
    description="Returns the job's script and media.",
    responses={200: {"description": "Composition data"}},
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
        script = json.loads(script_path.read_text(encoding="utf-8"))
    else:
        if not job.script:
            raise not_found_error()
        script = job.script

    # Load word timestamps
    words_path = job_dir / "words.json"
    words = json.loads(words_path.read_text(encoding="utf-8")) if words_path.exists() else []

    # Enumerate media files
    media_dir = job_dir / "media"
    media_urls = []
    if media_dir.exists():
        # Check for local template background first
        bg_file = media_dir / "background.mp4"
        if bg_file.exists():
            media_urls = [sign_media_url(f"/storage/jobs/{job_id}/media/background.mp4")]
        else:
            for i in range(len(script.get("scenes", []))):
                scene_file = media_dir / f"scene_{i}.mp4"
                if scene_file.exists():
                    media_urls.append(sign_media_url(f"/storage/jobs/{job_id}/media/scene_{i}.mp4"))

    if not media_urls:
        images_dir = job_dir / "images"
        if images_dir.exists():
            for p in sorted(images_dir.glob("scene_*.png"), key=scene_sort_key):
                media_urls.append(sign_media_url(f"/storage/jobs/{job_id}/images/{p.name}"))

    audio_url = sign_media_url(f"/storage/jobs/{job_id}/narration.wav") if (job_dir / "narration.wav").exists() else ""

    # Load editor state from DB if exists
    editor_state = job.editor_state

    # Get template info
    from app.templates import get_template

    job_template_id = getattr(job, "template_id", "stock_narration")
    tmpl = get_template(job_template_id)
    from app.job_config import resolve_job_flag
    from app.services.music import auto_music_url

    music_on = resolve_job_flag(_redis, job_id, "music_enabled", settings.AUTO_MUSIC_ENABLED)
    default_music_url = auto_music_url(job_template_id) if music_on else None

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
        music_url=default_music_url,
        music_volume=settings.AUTO_MUSIC_VOLUME,
    )


@router.post(
    "/jobs/{job_id}/edit",
    summary="Save edit",
    description="Saves current editor state.",
    responses={200: {"description": "Saved"}},
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
            state_path.write_text(json.dumps(req.editor_state, ensure_ascii=False, indent=2), encoding="utf-8")

            # Sync scenes/words to their own files
            comp = req.editor_state.get("composition", {})
            script_path = job_dir / "script.json"
            if script_path.exists() and comp.get("scenes"):
                script = json.loads(script_path.read_text(encoding="utf-8"))
                script["scenes"] = comp["scenes"]
                script_path.write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
                # Espelha o script editado no Postgres: sem isso ha split-brain
                # (j.script guarda o roteiro ORIGINAL da geracao para sempre e os
                # fallbacks de get_job/list_jobs servem versao velha pos-edicao).
                await db.execute(update(Job).where(Job.id == job.id).values(script=script))
                await db.commit()
            if comp.get("words"):
                words_path = job_dir / "words.json"
                words_path.write_text(json.dumps(comp["words"], ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.warning(f"Could not sync editor state to disk for {job_id}: {e}")

    return {"status": "saved"}


@router.post(
    "/jobs/{job_id}/regenerate-tts",
    summary="Regenerate TTS",
    description="Regenerates the video narration.",
    responses={200: {"description": "Regenerated"}},
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

    script = json.loads(script_path.read_text(encoding="utf-8"))
    narration = req.text if req.text else script.get("narration", "")

    # Regenerate TTS (async). ElevenLabs e pago -> cobra credito; Edge e gratuito -> sem debito.
    audio_path = str(job_dir / "narration.wav")
    if req.voice_provider == "elevenlabs":
        if not settings.ELEVENLABS_API_KEY:
            raise HTTPException(status_code=503, detail="ELEVENLABS_API_KEY not configured")
        from app.services.elevenlabs_provider import ElevenLabsProvider

        cost = settings.CREDIT_COST_ELEVENLABS
        await _debit_credits(db, user.id, cost)
        provider = ElevenLabsProvider()
        try:
            await provider.synthesize(
                text=narration,
                output_path=audio_path,
                voice_id=req.voice_id or "",
            )
        except Exception as e:  # noqa: BLE001
            await _refund_credits(db, user.id, cost)
            logger.warning("Regenerate TTS (ElevenLabs) falhou: %s", e)
            raise HTTPException(status_code=502, detail=f"Não foi possível regenerar a narração: {e}")
    else:
        from app.services.edge_provider import EDGE_VOICES
        from app.services.tts import synthesize_narration_async

        voice_id = req.voice_id or "pt-BR-AntonioNeural"
        if voice_id not in {voice.id for voice in EDGE_VOICES}:
            raise HTTPException(status_code=422, detail=ErrorMessages.INVALID_INPUT)

        await synthesize_narration_async(
            text=narration,
            output_path=audio_path,
            voice_id=voice_id,
            rate=req.rate if req.rate is not None else -10,
            pitch=req.pitch if req.pitch is not None else 5,
        )

    # Re-transcribe with Whisper (keep old words as fallback)
    words_path = job_dir / "words.json"
    old_words = json.loads(words_path.read_text(encoding="utf-8")) if words_path.exists() else []
    words = []
    try:
        from app.services.transcriber import transcribe_with_timestamps

        # to_thread: transcribe (Whisper/Groq) e sincrono e travaria o event loop sem isso.
        words = await asyncio.to_thread(transcribe_with_timestamps, audio_path)
    except Exception as e:
        logger.warning(f"Whisper transcription failed, keeping old timestamps: {e}")
        words = old_words

    # Save updated words
    if words:
        words_path.write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")

    return {
        "audio_url": sign_media_url(f"/storage/jobs/{job_id}/narration.wav"),
        "words": words,
    }


@router.post(
    "/jobs/{job_id}/ai-suggest",
    summary="AI Suggestions",
    description="Suggests edits using AI.",
    responses={200: {"description": "Suggestions"}},
)
async def ai_suggest(
    job_id: str,
    req: AISuggestRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get AI suggestions for script improvement. Acumula 0.5 credito por chamada."""
    job = await get_owned_job(db, user, job_id)

    script_json = json.dumps(req.context, ensure_ascii=False, indent=2) if req.context else "{}"

    prompt = f"""Voce e um editor de video especialista em conteudo viral para TikTok, Reels e Shorts.

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
- Maximo 3 sugestoes por resposta"""

    # asyncio.to_thread: complete_text usa o cliente OpenRouter SINCRONO (15-40s). Rodar direto no
    # handler async travaria o event loop inteiro -> Cloudflare estoura ~100s -> 502 em TODA requisicao
    # em voo (inclusive o polling de geracao). Em thread separada o loop fica livre.
    try:
        raw = await asyncio.to_thread(complete_text, prompt)
    except Exception as e:  # noqa: BLE001
        logger.warning("ai_suggest LLM falhou: %s", e)
        raise HTTPException(
            status_code=502,
            detail="A IA está indisponível no momento. Tente novamente em instantes.",
        )
    raw = strip_code_fences(raw)

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
    responses={200: {"description": "Render queued"}},
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
        # Re-le o estado fresco DENTRO do lock: cada request concorrente carregou seu proprio
        # job ANTES do lock, entao um render paralelo ja pode ter zerado o pending. commit encerra
        # a transacao de leitura -> refresh enxerga o que o concorrente commitou (cobra so 1x).
        await db.commit()
        await db.refresh(job)
        cost = math.ceil(job.pending_credits or 0.0)
        if cost > 0:
            await _debit_credits(db, user.id, cost)  # atomico: 402 se sem saldo, sem read-modify-write
            job.pending_credits = 0.0
            await db.commit()

    job_dir = Path(settings.STORAGE_DIR) / "jobs" / job_id
    if not job_dir.exists():
        raise not_found_error()

    from app.worker.tasks import task_rerender_video

    # Marca "rendering" ANTES de enfileirar: entre o POST e o worker (--pool=solo, fila
    # pode estar ocupada) o Redis ainda diria "completed" do pipeline original e o poll
    # do editor declararia o re-render concluido sem ele ter comecado (baixava a versao
    # pre-edicao). Setar antes do .delay evita sobrescrever o progresso real do worker.
    _redis.hset(
        f"job:{job_id}",
        mapping={
            "status": "rendering",
            "progress": 0.0,
            "current_step": "queued",
            "detail": "Re-render enfileirado...",
        },
    )
    try:
        task_rerender_video.delay(job_id)
    except Exception as e:  # noqa: BLE001 — enfileirar falhou (Celery/Redis down): estorna e reverte
        if cost > 0:
            await _refund_credits(db, user.id, cost)
            job.pending_credits = float(cost)  # restaura p/ a re-tentativa cobrar de novo
            await db.commit()
        _redis.hset(
            f"job:{job_id}",
            mapping={"status": "completed", "detail": "Re-render nao pode ser enfileirado; credito estornado."},
        )
        logger.error("task_rerender_video.delay falhou job=%s: %s — credito estornado", job_id, e)
        raise HTTPException(
            status_code=503,
            detail="Nao foi possivel iniciar o re-render agora. Seu credito foi estornado, tente novamente.",
        )

    return {
        "status": "rendering",
        "message": "Re-render iniciado com edicoes atuais.",
    }


@router.post(
    "/jobs/{job_id}/reset",
    summary="Reset job",
    description="Resets job state to defaults.",
    responses={200: {"description": "Reset successfully"}},
)
async def reset_job(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reset job to original state. Costs 1 credit, clears pending_credits."""
    job = await get_owned_job(db, user, job_id)
    async with get_lock(f"reset:{job_id}"):
        await _debit_credits(db, user.id, 1)  # atomico: 402 se sem saldo, sem read-modify-write
        job.pending_credits = 0.0
        job.editor_state = None
        await db.commit()
        fresh_user = await db.get(User, user.id)
        return {"status": "reset", "credits_remaining": fresh_user.credits}


@router.get(
    "/jobs/{job_id}/status",
    summary="Job status",
    description="Gets job status from Redis.",
    responses={200: {"description": "Status"}},
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
    responses={200: {"description": "Cancel initiated"}},
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
    "/jobs", summary="List jobs", description="List user's jobs.", responses={200: {"description": "List of jobs"}}
)
async def list_jobs(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all jobs for the current user, with real-time status from Redis."""
    result = await db.execute(select(Job).where(Job.user_id == user.id).order_by(Job.created_at.desc()).limit(50))
    jobs = result.scalars().all()

    # Fila global p/ "N na frente" (worker solo = 1 por vez). O Postgres fica
    # "queued" durante todo o processamento, entao ele lista os candidatos; o
    # Redis diz quem segue ativo de verdade (o job rodando tambem conta na fila).
    # Lazy: so paga o custo quando o usuario tem job aguardando.
    live_queue: list | None = None

    async def _queue_ahead_of(created_at) -> int | None:
        nonlocal live_queue
        if created_at is None:
            return None
        if live_queue is None:
            q = await db.execute(
                select(Job.id, Job.created_at).where(Job.status == "queued").order_by(Job.created_at).limit(200)
            )
            live_queue = []
            for jid, jcreated in q.all():
                live = _redis.hgetall(f"job:{jid}")
                live_status = live.get("status") if live else None
                # sem hash = ainda nem comecou (na fila); ativos seguem na conta
                if live_status in (None, "", "queued", "processing", "rendering"):
                    live_queue.append(jcreated)
        return sum(1 for other in live_queue if other and other < created_at)

    items = []
    for j in jobs:
        # Redis has the real-time status; DB may be stale
        redis_data = _redis.hgetall(f"job:{j.id}")
        status = redis_data.get("status", j.status) if redis_data else j.status
        has_video = j.video_url or (Path(settings.STORAGE_DIR) / "output" / f"{j.id}.mp4").exists()
        # Em estado ativo o arquivo em output/ pode ser a versao ANTIGA (re-render em
        # andamento): esconder o download fecha pelo dashboard a mesma corrida que o
        # editor fecha via get_job (baixar video pre-edicao).
        downloadable = has_video and status not in {"queued", "processing", "rendering", "cancelling"}
        # Treat completed jobs as editable if they have composition files
        if status == "completed":
            job_dir = Path(settings.STORAGE_DIR) / "jobs" / str(j.id)
            if (job_dir / "script.json").exists():
                status = "editable"
        items.append(
            {
                "job_id": str(j.id),
                "topic": j.topic,
                "style": j.style,
                "status": status,
                "duration_target": j.duration_target,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "download_url": f"/api/v1/jobs/{j.id}/download" if downloadable else None,
                # Poster do card (gerado no finalize; ausente em jobs antigos -> fallback no front)
                "thumbnail_url": (
                    f"/api/v1/jobs/{j.id}/thumbnail"
                    if (Path(settings.STORAGE_DIR) / "output" / f"{j.id}.jpg").exists()
                    else None
                ),
                # Progresso em tempo real p/ a grid reativa (o hash do Redis ja esta em maos).
                "progress": float(redis_data.get("progress") or 0) if redis_data else 0.0,
                "current_step": (redis_data.get("current_step") or None) if redis_data else None,
                # Q7: roteiro atendido pelo provedor free (badge de qualidade reduzida no card).
                # Redis = tempo real; script JSONB = durabilidade (sobrevive a reboot do Redis).
                "degraded": (redis_data.get("degraded") == "1" if redis_data else False)
                or (isinstance(j.script, dict) and j.script.get("llm_provider") == "openrouter-free"),
                # Posicao honesta na fila do worker (solo): so para quem esta aguardando.
                "queue_position": (await _queue_ahead_of(j.created_at)) if status == "queued" else None,
            }
        )
    return items


@router.get(
    "/admin/economy",
    summary="Economia por job",
    description="Custo estimado de API vs créditos cobrados, por job e por template.",
    responses={200: {"description": "Telemetria de economia"}},
)
async def admin_economy(
    _admin_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Margem real da operação: telemetria consolidada no finalize de cada job.
    Jobs antigos (sem telemetry) ficam de fora — a visão cresce com o uso."""
    result = await db.execute(select(Job).where(Job.telemetry.isnot(None)).order_by(Job.created_at.desc()).limit(100))
    jobs = result.scalars().all()

    items = []
    by_template: dict[str, dict] = {}
    for j in jobs:
        tel = j.telemetry or {}
        cost = float(tel.get("api_cost_usd_est") or 0.0)
        rerenders = tel.get("rerenders") or []
        items.append(
            {
                "job_id": str(j.id),
                "template_id": j.template_id,
                "voice_provider": j.voice_provider,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "total_seconds": tel.get("total_seconds"),
                "steps": tel.get("steps") or {},
                "api_cost_usd_est": cost,
                "credit_cost": j.credit_cost,
                "rerenders": len(rerenders),
                "rerender_seconds": round(sum(float(r.get("duration_seconds") or 0.0) for r in rerenders), 1),
            }
        )
        agg = by_template.setdefault(
            j.template_id, {"count": 0, "api_cost_usd_est": 0.0, "credits": 0, "total_seconds": 0.0}
        )
        agg["count"] += 1
        agg["api_cost_usd_est"] = round(agg["api_cost_usd_est"] + cost, 4)
        agg["credits"] += j.credit_cost or 0
        agg["total_seconds"] += float(tel.get("total_seconds") or 0.0)

    for agg in by_template.values():
        n = agg["count"] or 1
        agg["avg_cost_usd"] = round(agg["api_cost_usd_est"] / n, 4)
        agg["avg_seconds"] = round(agg["total_seconds"] / n, 1)

    return {"jobs": items, "by_template": by_template}


@router.get(
    "/admin/dashboard",
    summary="Admin dashboard",
    description="Aggregated admin metrics for the SaaS control panel.",
    responses={200: {"description": "Dashboard metrics"}},
)
async def admin_dashboard(
    range: str = "30d",
    _admin_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    if range not in _ADMIN_DASHBOARD_RANGES:
        raise HTTPException(status_code=400, detail="Range invalido")

    now = datetime.now(timezone.utc)
    days = _ADMIN_DASHBOARD_RANGES[range]
    window_start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)

    # SQL-filtered queries — only load rows within the time window
    users_result = await db.execute(select(User).where(User.created_at >= window_start))
    users_in_range = list(users_result.scalars().all())

    purchases_result = await db.execute(select(CreditPurchase).where(CreditPurchase.created_at >= window_start))
    purchases_in_range = list(purchases_result.scalars().all())

    jobs_result = await db.execute(select(Job).where(Job.created_at >= window_start))
    jobs_in_range = list(jobs_result.scalars().all())

    # Aggregate totals via SQL — no need to load all rows
    approved_purchases = [purchase for purchase in purchases_in_range if purchase.status == "approved"]
    pending_purchases = [purchase for purchase in purchases_in_range if purchase.status != "approved"]

    approved_user_ids_result = await db.execute(
        select(CreditPurchase.user_id).where(CreditPurchase.status == "approved").distinct()
    )
    approved_user_ids = {str(uid) for uid in approved_user_ids_result.scalars().all()}

    # Job status counts via SQL GROUP BY
    job_status_rows = await db.execute(select(Job.status, func.count(Job.id)).group_by(Job.status))
    current_job_statuses: dict[str, int] = defaultdict(int, {row[0]: row[1] for row in job_status_rows.all()})

    # Pending credits via SQL aggregation — only jobs that have pending_credits > 0
    pending_credits_result = await db.execute(select(Job.pending_credits).where(Job.pending_credits > 0))
    pending_credits_jobs = [float(v) for v in pending_credits_result.scalars().all()]

    # Recent activity via SQL ORDER BY + LIMIT (avoids loading full tables)
    recent_users_result = await db.execute(select(User).order_by(User.created_at.desc()).limit(5))
    recent_users = list(recent_users_result.scalars().all())

    recent_purchases_result = await db.execute(
        select(CreditPurchase).order_by(CreditPurchase.created_at.desc()).limit(5)
    )
    recent_purchases = list(recent_purchases_result.scalars().all())

    recent_failed_jobs_result = await db.execute(
        select(Job).where(Job.status == "failed").order_by(Job.created_at.desc()).limit(5)
    )
    recent_failed_jobs = list(recent_failed_jobs_result.scalars().all())

    revenue_by_day = _empty_daily_series(days, now)
    users_by_day = _empty_daily_series(days, now)
    jobs_by_day = _empty_daily_series(days, now)
    approved_orders_by_day = _empty_daily_series(days, now)

    package_mix: dict[str, dict[str, int | float | str]] = {}

    for user in users_in_range:
        bucket = _bucket_key(user.created_at)
        if bucket:
            users_by_day[bucket] += 1

    for purchase in purchases_in_range:
        bucket = _bucket_key(purchase.created_at)
        if bucket:
            if purchase.status == "approved":
                revenue_by_day[bucket] += purchase.price_brl / 100
                approved_orders_by_day[bucket] += 1

        mix = package_mix.setdefault(
            purchase.package_name,
            {
                "package_name": purchase.package_name,
                "orders": 0,
                "approved_revenue_brl": 0.0,
                "credits_sold": 0,
            },
        )
        mix["orders"] += 1
        if purchase.status == "approved":
            mix["approved_revenue_brl"] = _round2(float(mix["approved_revenue_brl"]) + (purchase.price_brl / 100))
            mix["credits_sold"] = int(mix["credits_sold"]) + purchase.credits_amount

    for job in jobs_in_range:
        bucket = _bucket_key(job.created_at)
        if bucket:
            jobs_by_day[bucket] += 1

    settled_jobs = [job for job in jobs_in_range if job.status in {"completed", "failed"}]
    success_rate = 0.0
    if settled_jobs:
        success_rate = _round2((sum(1 for job in settled_jobs if job.status == "completed") / len(settled_jobs)) * 100)

    avg_pending_credits = (
        _round2(sum(pending_credits_jobs) / len(pending_credits_jobs)) if pending_credits_jobs else 0.0
    )

    storage_stats = await _build_storage_stats(db)

    approved_revenue_brl = _round2(sum(purchase.price_brl for purchase in approved_purchases) / 100)
    pending_revenue_brl = _round2(sum(purchase.price_brl for purchase in pending_purchases) / 100)
    approved_orders = len(approved_purchases)
    average_ticket_brl = _round2(approved_revenue_brl / approved_orders) if approved_orders else 0.0
    verified_users = sum(1 for user in users_in_range if user.email_verified)
    paying_users = len({str(purchase.user_id) for purchase in approved_purchases})
    registered = len(users_in_range)
    verification_rate = _round2((verified_users / registered) * 100) if registered else 0.0
    payer_conversion_rate = _round2((paying_users / registered) * 100) if registered else 0.0

    return {
        "range": range,
        "window_start": window_start.date().isoformat(),
        "window_end": now.date().isoformat(),
        "summary": {
            "approved_revenue_brl": approved_revenue_brl,
            "pending_revenue_brl": pending_revenue_brl,
            "approved_orders": approved_orders,
            "pending_orders": len(pending_purchases),
            "average_ticket_brl": average_ticket_brl,
            "new_users": registered,
            "verified_users": verified_users,
            "paying_users": paying_users,
            "active_jobs": int(current_job_statuses["queued"] + current_job_statuses["processing"]),
            "credits_sold": int(sum(purchase.credits_amount for purchase in approved_purchases)),
            "credits_consumed": int(len(jobs_in_range)),
        },
        "timeseries": {
            "revenue_by_day": [{"date": date, "value": _round2(value)} for date, value in revenue_by_day.items()],
            "new_users_by_day": [{"date": date, "value": int(value)} for date, value in users_by_day.items()],
            "jobs_by_day": [{"date": date, "value": int(value)} for date, value in jobs_by_day.items()],
            "approved_orders_by_day": [
                {"date": date, "value": int(value)} for date, value in approved_orders_by_day.items()
            ],
        },
        "funnel": {
            "registered": registered,
            "verified": verified_users,
            "paying": paying_users,
            "verification_rate": verification_rate,
            "payer_conversion_rate": payer_conversion_rate,
        },
        "operations": {
            "queued_jobs": int(current_job_statuses["queued"]),
            "processing_jobs": int(current_job_statuses["processing"]),
            "completed_jobs": int(current_job_statuses["completed"]),
            "failed_jobs": int(current_job_statuses["failed"]),
            "success_rate": success_rate,
            "avg_pending_credits": avg_pending_credits,
            **storage_stats,
        },
        "package_mix": sorted(
            package_mix.values(),
            key=lambda item: (float(item["approved_revenue_brl"]), int(item["orders"])),
            reverse=True,
        ),
        "recent_activity": {
            "recent_users": [
                {
                    "id": str(user.id),
                    "email": user.email,
                    "name": user.name,
                    "plan": user.plan,
                    "email_verified": user.email_verified,
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                    "is_paying": str(user.id) in approved_user_ids,
                }
                for user in recent_users
            ],
            "recent_purchases": [
                {
                    "id": str(purchase.id),
                    "user_id": str(purchase.user_id),
                    "package_name": purchase.package_name,
                    "price_brl": purchase.price_brl,
                    "credits_amount": purchase.credits_amount,
                    "status": purchase.status,
                    "created_at": purchase.created_at.isoformat() if purchase.created_at else None,
                    "paid_at": purchase.paid_at.isoformat() if purchase.paid_at else None,
                }
                for purchase in recent_purchases
            ],
            "recent_failed_jobs": [
                {
                    "id": str(job.id),
                    "user_id": str(job.user_id),
                    "topic": job.topic,
                    "status": job.status,
                    "error": job.error,
                    "created_at": job.created_at.isoformat() if job.created_at else None,
                }
                for job in recent_failed_jobs
            ],
        },
    }


@router.get(
    "/admin/storage-stats",
    summary="Storage stats",
    description="Admin storage stats.",
    responses={200: {"description": "Stats"}},
)
async def storage_stats(
    _admin_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    return await _build_storage_stats(db)


def _admin_pagination(page: int, page_size: int) -> tuple[int, int]:
    """Clamp de paginacao dos endpoints admin (page >= 1, page_size 1..100)."""
    return max(1, page), min(max(1, page_size), 100)


@router.get(
    "/admin/users",
    summary="Admin: list users",
    description="Paginated user list with search by email/name.",
    responses={200: {"description": "Users"}},
)
async def admin_list_users(
    search: str = "",
    page: int = 1,
    page_size: int = 50,
    _admin_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    page, page_size = _admin_pagination(page, page_size)
    stmt = select(User)
    count_stmt = select(func.count()).select_from(User)
    if search.strip():
        like = f"%{search.strip()}%"
        cond = User.email.ilike(like) | User.name.ilike(like)
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    total = (await db.execute(count_stmt)).scalar() or 0
    rows = await db.execute(stmt.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
    users = list(rows.scalars().all())

    paying: set[str] = set()
    if users:
        paying_rows = await db.execute(
            select(CreditPurchase.user_id)
            .where(CreditPurchase.user_id.in_([u.id for u in users]), CreditPurchase.status == "approved")
            .distinct()
        )
        paying = {str(uid) for uid in paying_rows.scalars().all()}

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "users": [
            {
                "id": str(u.id),
                "email": u.email,
                "name": u.name,
                "credits": u.credits,
                "plan": u.plan,
                "email_verified": u.email_verified,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "is_paying": str(u.id) in paying,
            }
            for u in users
        ],
    }


@router.get(
    "/admin/purchases",
    summary="Admin: list purchases",
    description="Paginated purchase list with status filter.",
    responses={200: {"description": "Purchases"}},
)
async def admin_list_purchases(
    status: str = "",
    page: int = 1,
    page_size: int = 50,
    _admin_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    page, page_size = _admin_pagination(page, page_size)
    stmt = select(CreditPurchase, User.email).join(User, CreditPurchase.user_id == User.id)
    count_stmt = select(func.count()).select_from(CreditPurchase)
    if status.strip():
        stmt = stmt.where(CreditPurchase.status == status.strip())
        count_stmt = count_stmt.where(CreditPurchase.status == status.strip())

    total = (await db.execute(count_stmt)).scalar() or 0
    rows = await db.execute(
        stmt.order_by(CreditPurchase.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "purchases": [
            {
                "id": str(p.id),
                "user_email": email,
                "package_name": p.package_name,
                "credits_amount": p.credits_amount,
                "bonus_credits": p.bonus_credits,
                "price_brl": p.price_brl,
                "provider": p.provider,
                "status": p.status,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "paid_at": p.paid_at.isoformat() if p.paid_at else None,
            }
            for p, email in rows.all()
        ],
    }


@router.get(
    "/admin/jobs",
    summary="Admin: list jobs",
    description="Paginated job list with status filter.",
    responses={200: {"description": "Jobs"}},
)
async def admin_list_jobs(
    status: str = "",
    page: int = 1,
    page_size: int = 50,
    _admin_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    page, page_size = _admin_pagination(page, page_size)
    stmt = select(Job, User.email).join(User, Job.user_id == User.id)
    count_stmt = select(func.count()).select_from(Job)
    if status.strip():
        stmt = stmt.where(Job.status == status.strip())
        count_stmt = count_stmt.where(Job.status == status.strip())

    total = (await db.execute(count_stmt)).scalar() or 0
    rows = await db.execute(stmt.order_by(Job.created_at.desc()).offset((page - 1) * page_size).limit(page_size))

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "jobs": [
            {
                "id": str(j.id),
                "user_email": email,
                "topic": j.topic,
                "template_id": j.template_id,
                "status": j.status,
                "credit_cost": j.credit_cost,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "error": j.error,
            }
            for j, email in rows.all()
        ],
    }


@router.post(
    "/feedback",
    status_code=201,
    summary="Submit feedback",
    description="User feedback: in-app widget (rating 1-5 + comment) or post-video prompt (per job).",
    responses={201: {"description": "Saved"}},
)
@limiter.limit("5/minute")
async def submit_feedback(
    request: Request,
    req: FeedbackRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job_uuid = None
    if req.job_id:
        job_uuid = validate_uuid(req.job_id)
        job = await db.get(Job, job_uuid)
        if not job or job.user_id != user.id:
            raise not_found_error()

    db.add(
        Feedback(
            user_id=user.id,
            kind=req.kind,
            rating=req.rating,
            comment=(req.comment or "").strip() or None,
            job_id=job_uuid,
            source_url=req.source_url,
        )
    )
    await db.commit()
    return {"status": "ok"}


@router.get(
    "/admin/feedbacks",
    summary="Admin: list feedbacks",
    description="Paginated feedback list with kind filter.",
    responses={200: {"description": "Feedbacks"}},
)
async def admin_list_feedbacks(
    kind: str = "",
    page: int = 1,
    page_size: int = 50,
    _admin_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    page, page_size = _admin_pagination(page, page_size)
    stmt = (
        select(Feedback, User.email, Job.topic)
        .join(User, Feedback.user_id == User.id)
        .outerjoin(Job, Feedback.job_id == Job.id)
    )
    count_stmt = select(func.count()).select_from(Feedback)
    if kind.strip():
        stmt = stmt.where(Feedback.kind == kind.strip())
        count_stmt = count_stmt.where(Feedback.kind == kind.strip())

    total = (await db.execute(count_stmt)).scalar() or 0
    rows = await db.execute(stmt.order_by(Feedback.created_at.desc()).offset((page - 1) * page_size).limit(page_size))

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "feedbacks": [
            {
                "id": str(f.id),
                "user_email": email,
                "kind": f.kind,
                "rating": f.rating,
                "comment": f.comment,
                "job_id": str(f.job_id) if f.job_id else None,
                "job_topic": topic,
                "source_url": f.source_url,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f, email, topic in rows.all()
        ],
    }


@router.post(
    "/admin/users/{user_id}/adjust-credits",
    summary="Admin: adjust user credits",
    description="Manually add/remove credits with mandatory reason (audited in credit_adjustments).",
    responses={200: {"description": "Adjusted"}},
)
async def admin_adjust_credits(
    user_id: str,
    req: AdminCreditAdjustRequest,
    admin_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    target = await db.get(User, validate_uuid(user_id))
    if not target:
        raise not_found_error()

    previous = target.credits
    new_balance = max(0, previous + req.delta)  # clamp: saldo nunca fica negativo
    target.credits = new_balance
    db.add(
        CreditAdjustment(
            admin_user_id=admin_user.id,
            target_user_id=target.id,
            delta=req.delta,
            reason=req.reason.strip(),
            previous_balance=previous,
            new_balance=new_balance,
        )
    )
    await db.commit()

    applied = new_balance - previous
    if applied:
        record_credit_metric("credit" if applied > 0 else "debit", abs(applied))
    logger.warning(
        "Admin %s ajustou creditos de %s: %+d (%d -> %d) motivo=%s",
        admin_user.email,
        target.email,
        req.delta,
        previous,
        new_balance,
        req.reason.strip(),
    )
    return {
        "user_id": str(target.id),
        "delta": req.delta,
        "previous_balance": previous,
        "new_balance": new_balance,
    }


@router.get(
    "/public/stats",
    summary="Public stats",
    description="Public platform statistics for landing page.",
    responses={200: {"description": "Stats"}},
)
@limiter.limit("30/minute")
async def public_stats(request: Request, db: AsyncSession = Depends(get_db)):
    """Return public stats (total videos generated). No auth required."""
    from sqlalchemy import func

    result = await db.execute(select(func.count()).select_from(Job).where(Job.status == "completed"))
    total_videos = result.scalar() or 0
    return {"total_videos": total_videos}
