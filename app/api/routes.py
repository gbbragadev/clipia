import asyncio
import json
import logging
import math
import shutil
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from slowapi import Limiter
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.service import append_server_event_safely
from app.api.security import get_owned_job
from app.auth.dependencies import get_current_admin_user, get_current_user
from app.config import settings
from app.credits import CREDIT_TARIFFS
from app.db.engine import get_db
from app.db.models import (
    AnalyticsEvent,
    CreditAdjustment,
    CreditPurchase,
    Feedback,
    Job,
    JobDispatch,
    User,
    VoiceClone,
    WaitlistEntry,
)
from app.errors import ErrorMessages, artifact_unavailable_error, not_found_error, validate_uuid
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
from app.payments.states import (
    canonical_payment_state_expression,
    canonical_payment_state_or_invalid,
)
from app.pricing import get_generation_credit_cost
from app.redis_pool import get_redis
from app.services.audio_uploads import (
    declared_audio_extension,
    parse_limited_multipart,
    read_limited_audio,
    write_limited_audio,
)
from app.services.credit_ledger import set_credit_ledger_context
from app.services.dispatch_outbox import DispatchPayload, create_dispatch, publish_dispatch
from app.services.job_operations import (
    InsufficientCredits,
    InvalidJobOperation,
    begin_rerender,
    mark_generation_dispatched,
    mark_rerender_dispatched,
    refund_generation,
    refund_rerender,
    request_generation_cancel,
)
from app.services.llm import complete_text, strip_code_fences
from app.services.refine_balance import (
    adjust_refine_balance,
    queue_refine_balance_projection,
    sync_refine_balance_projection,
)
from app.services.remotion import scene_sort_key
from app.services.trends import fetch_trends, get_example_topics
from app.templates import get_template
from app.utils.files import bytes_to_gb, cleanup_job_dir, get_job_dir, path_size_bytes
from app.utils.locks import get_lock
from app.utils.media_url import sign_media_url
from app.utils.ratelimit import client_ip
from app.worker.tasks import _send_admin_alert, dispatch_pipeline

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=client_ip)
router = APIRouter(tags=["jobs"])
_redis = get_redis()

_ADMIN_DASHBOARD_RANGES = {"7d": 7, "30d": 30, "90d": 90}
_ANALYTICS_NICHES = {"curiosidades", "religioso", "motivacional", "financas", "historias", "humor", "drama"}


def _validate_audio_upload(content_type: str | None, filename: str | None, size: int, max_mb: int = 50) -> str:
    """Validate audio upload. Returns safe extension. Raises ValueError on failure."""
    if size > max_mb * 1024 * 1024:
        raise ValueError(f"Arquivo muito grande (max {max_mb}MB)")
    return declared_audio_extension(content_type)


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


async def _debit_credits(
    db: AsyncSession,
    user_id,
    cost: int,
    commit: bool = True,
    *,
    action: str = "paid_operation",
    operation_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
) -> uuid.UUID | None:
    """Debito atomico de creditos (mesmo padrao da rota /generate).

    Faz UPDATE ... WHERE credits >= cost (sem read-modify-write) para evitar race/saldo negativo.
    Levanta 402 se nao houver saldo, 403 se o email nao estiver verificado. No-op se cost <= 0.
    commit=False deixa o caller commitar junto com as proprias mudancas (debito + estado do job
    na MESMA transacao — um erro no meio nao deixa credito cobrado sem o efeito aplicado).
    """
    if cost <= 0:
        return operation_id
    ledger_operation_id = operation_id or uuid.uuid4()
    await set_credit_ledger_context(
        db,
        origin=f"{action}_debit",
        reason=f"{action} reserved",
        idempotency_key=f"{action}:{ledger_operation_id}:debit",
        job_id=job_id,
        operation_id=ledger_operation_id,
    )
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
    if commit:
        await db.commit()
    record_credit_metric("debit", cost)
    return ledger_operation_id


async def _refund_credits(
    db: AsyncSession,
    user_id,
    cost: int,
    *,
    action: str,
    operation_id: uuid.UUID,
    job_id: uuid.UUID | None = None,
) -> None:
    """Devolve creditos quando uma operacao paga falha depois do debito. No-op se cost <= 0."""
    if cost <= 0:
        return
    await set_credit_ledger_context(
        db,
        origin=f"{action}_refund",
        reason=f"failed {action} refunded",
        idempotency_key=f"{action}:{operation_id}:refund",
        job_id=job_id,
        operation_id=operation_id,
    )
    await db.execute(update(User).where(User.id == user_id).values(credits=User.credits + cost))
    await db.commit()
    record_credit_metric("credit", cost)


async def _refund_credits_safe(
    db: AsyncSession,
    user_id,
    cost: int,
    action: str,
    operation_id: uuid.UUID,
    *,
    job_id: uuid.UUID | None = None,
) -> bool:
    """Refund que NUNCA levanta: uma excecao aqui substituiria o erro ORIGINAL da acao
    paga (o cliente veria 500 generico em vez da causa real) e deixaria o estorno perdido
    em silencio. Sessao suja ganha um rollback+retry; falhou de vez -> CRITICAL + alerta
    admin com os dados do estorno manual (mesmo contrato do worker, d23c0ec)."""
    try:
        await _refund_credits(
            db,
            user_id,
            cost,
            action=action,
            operation_id=operation_id,
            job_id=job_id,
        )
        return True
    except Exception:  # noqa: BLE001
        try:
            await db.rollback()
            await _refund_credits(
                db,
                user_id,
                cost,
                action=action,
                operation_id=operation_id,
                job_id=job_id,
            )
            return True
        except Exception:  # noqa: BLE001
            logger.critical(
                "Refund FALHOU: user=%s cost=%s action=%s — estorno manual necessario",
                user_id,
                cost,
                action,
                exc_info=True,
            )
            try:
                await asyncio.to_thread(
                    _send_admin_alert,
                    "ClipIA - refund FALHOU (estorno manual)",
                    f"user_id={user_id} cost={cost} action={action}. Estornar manualmente e investigar.",
                )
            except Exception:  # noqa: BLE001
                logger.exception("Falha ao enviar alerta admin de refund")
            return False


async def _lock_script_refine_balance(db: AsyncSession, user_id: uuid.UUID) -> tuple[User, uuid.UUID | None]:
    """Lock the SQL refine balance and lazily import the legacy Redis value once."""
    result = await db.execute(
        select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True)
    )
    locked_user = result.scalar_one_or_none()
    if locked_user is None:
        raise HTTPException(status_code=401, detail=ErrorMessages.UNAUTHORIZED)
    if locked_user.script_refine_redis_migrated:
        return locked_user, None

    legacy_key = f"script_refine_pending:{user_id}"
    legacy_version_key = f"script_refine_pending_version:{user_id}"
    try:
        raw_legacy = _redis.get(legacy_key)
        raw_legacy_version = _redis.get(legacy_version_key)
        legacy_pending = float(raw_legacy or 0.0)
        legacy_version = int(raw_legacy_version or 0)
        if not math.isfinite(legacy_pending) or legacy_pending < 0:
            raise ValueError("invalid legacy refine balance")
        if legacy_version < 0:
            raise ValueError("invalid legacy refine version")
    except Exception as exc:  # noqa: BLE001 - unknown legacy debt must never be discarded
        logger.error("Falha ao importar saldo legado de refino user=%s: %s", user_id, exc)
        raise HTTPException(status_code=503, detail="Nao foi possivel reservar o saldo de refinos agora.") from exc

    locked_user.script_refine_pending = round(float(locked_user.script_refine_pending or 0.0) + legacy_pending, 2)
    locked_user.script_refine_version = (
        max(
            int(locked_user.script_refine_version or 0),
            legacy_version,
        )
        + 1
    )
    locked_user.script_refine_redis_migrated = True
    projection = await queue_refine_balance_projection(
        db,
        user_id=user_id,
        version=locked_user.script_refine_version,
        balance_after=locked_user.script_refine_pending,
    )
    return locked_user, projection.id


async def _sync_refine_projection_best_effort(db: AsyncSession, projection_id: uuid.UUID | None) -> None:
    if projection_id is None:
        return
    try:
        await sync_refine_balance_projection(db, projection_id, _redis)
    except Exception:  # noqa: BLE001 - the committed outbox is drained independently
        await db.rollback()
        logger.exception("Falha ao projetar saldo de refino; outbox permanece para drain id=%s", projection_id)


def _release_generation_quota(cap_key: str | None, reserved: bool) -> None:
    if not cap_key or not reserved:
        return
    try:
        _redis.decr(cap_key)
    except Exception:  # noqa: BLE001 - SQL refund must not be hidden by Redis cleanup
        logger.exception("Falha ao devolver quota de geracao key=%s", cap_key)


async def _classify_dispatch_after_refund_cas(
    db: AsyncSession,
    *,
    job_id: uuid.UUID,
    dispatch_id: uuid.UUID,
    kind: str,
    operation_id: uuid.UUID,
) -> str:
    """Classify CAS=False without turning accepted work into a manual refund."""
    try:
        await db.rollback()
        job_result = await db.execute(
            select(Job).where(Job.id == job_id).with_for_update().execution_options(populate_existing=True)
        )
        job = job_result.scalar_one_or_none()
        dispatch_result = await db.execute(
            select(JobDispatch)
            .where(
                JobDispatch.id == dispatch_id,
                JobDispatch.job_id == job_id,
                JobDispatch.kind == kind,
                JobDispatch.operation_id == operation_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        dispatch = dispatch_result.scalar_one_or_none()
        financially_refunded = job is not None and (
            (kind == "generation" and job.generation_refunded_at is not None)
            or (kind == "rerender" and job.rerender_state == "refunded")
        )
        exact_dispatch_cancelled = dispatch is not None and dispatch.state == "cancelled"
        delivered = (dispatch is not None and dispatch.state == "completed") or (
            job is not None
            and (
                (
                    kind == "generation"
                    and (
                        job.video_url is not None
                        or job.completed_at is not None
                        or job.status in {"editable", "completed"}
                    )
                )
                or (kind == "rerender" and job.rerender_state == "completed")
            )
        )
        active_dispatch = dispatch is not None and (
            dispatch.claimed_at is not None or dispatch.state in {"published", "claimed"}
        )
        if financially_refunded or exact_dispatch_cancelled:
            outcome = "already_refunded"
        elif delivered or active_dispatch:
            outcome = "accepted_or_completed"
        else:
            outcome = "refund_pending"
        await db.rollback()
        return outcome
    except Exception:  # noqa: BLE001 - an unreadable DB means financial state is unresolved
        await db.rollback()
        logger.exception("Falha ao classificar compensation job=%s dispatch=%s", job_id, dispatch_id)
        return "refund_pending"


async def _compensate_generation_dispatch(
    db: AsyncSession,
    *,
    job_id: uuid.UUID,
    cap_key: str | None,
    quota_reserved: bool,
    credit_cost: int,
    error: Exception,
    dispatch_id: uuid.UUID,
) -> str:
    refunded = False
    for attempt in range(2):
        try:
            refunded = await refund_generation(
                db,
                job_id,
                status="failed",
                error="Falha ao enfileirar a geracao. Credito estornado.",
                outbox_dispatch_id=dispatch_id,
            )
            await db.commit()
            break
        except Exception:  # noqa: BLE001 - rollback and one retry before escalating
            await db.rollback()
            if attempt == 1:
                logger.critical("Refund persistente falhou job=%s", job_id, exc_info=True)

    if refunded:
        outcome = "refunded"
        record_credit_metric("credit", credit_cost)
    else:
        outcome = await _classify_dispatch_after_refund_cas(
            db,
            job_id=job_id,
            dispatch_id=dispatch_id,
            kind="generation",
            operation_id=job_id,
        )
    if outcome == "accepted_or_completed":
        logger.warning("Compensation ignorada: dispatch aceito job=%s dispatch=%s", job_id, dispatch_id)
        return outcome
    if outcome == "refund_pending":
        try:
            await asyncio.to_thread(
                _send_admin_alert,
                "ClipIA - compensation requer reconciliacao",
                f"job_id={job_id} error={error!r}. Acompanhar outbox/reconciliador; "
                "nao ajustar saldo manualmente sem confirmar o estado idempotente.",
            )
        except Exception:  # noqa: BLE001
            logger.exception("Falha ao alertar compensation manual job=%s", job_id)
        try:
            _redis.hset(
                f"job:{job_id}",
                mapping={
                    "status": "refund_pending",
                    "error": "Falha ao enfileirar a geracao. Estorno persistente pendente.",
                    "generation_broker_state": "failed",
                },
            )
        except Exception:  # noqa: BLE001 - DB reconciliation remains authoritative
            logger.exception("Falha ao publicar refund_pending job=%s", job_id)
        return outcome

    cleanup_job_dir(str(job_id))
    if outcome == "refunded":
        # Only the request that won the refund CAS owns this non-idempotent
        # decrement. An already-refunded worker race is cleaned up, but its
        # quota reservation is left to expire instead of risking a double DECR.
        _release_generation_quota(cap_key, quota_reserved)
    try:
        message = "Falha ao enfileirar a geracao. Credito estornado."
        _redis.hset(
            f"job:{job_id}",
            mapping={
                "status": "failed",
                "error": message,
                "generation_broker_state": "failed",
            },
        )
    except Exception:  # noqa: BLE001 - terminal Redis state is best-effort; DB is authoritative
        logger.exception("Falha ao publicar estado Redis compensado job=%s", job_id)
    return outcome


async def _compensate_rerender_dispatch(
    db: AsyncSession,
    *,
    job_id: uuid.UUID,
    operation_id: uuid.UUID,
    dispatch_id: uuid.UUID,
) -> str:
    refunded = False
    for attempt in range(2):
        try:
            refunded = await refund_rerender(
                db,
                job_id,
                operation_id,
                outbox_dispatch_id=dispatch_id,
            )
            await db.commit()
            break
        except Exception:  # noqa: BLE001 - rollback and one retry before durable reconciliation
            await db.rollback()
            if attempt == 1:
                logger.critical("Refund de rerender falhou job=%s op=%s", job_id, operation_id, exc_info=True)
    if refunded:
        return "refunded"
    outcome = await _classify_dispatch_after_refund_cas(
        db,
        job_id=job_id,
        dispatch_id=dispatch_id,
        kind="rerender",
        operation_id=operation_id,
    )
    if outcome == "accepted_or_completed":
        logger.warning(
            "Compensation de rerender ignorada: dispatch aceito job=%s op=%s",
            job_id,
            operation_id,
        )
        return outcome
    if outcome == "refund_pending":
        try:
            await asyncio.to_thread(
                _send_admin_alert,
                "ClipIA - refund de rerender falhou",
                f"job_id={job_id} operation_id={operation_id}. Verificar reconciliacao, sem duplicar credito.",
            )
        except Exception:  # noqa: BLE001
            logger.exception("Falha ao alertar refund de rerender job=%s", job_id)
    return outcome


@router.post(
    "/generate",
    summary="Generate a video",
    description="Starts a new video generation job.",
    status_code=202,
    responses={202: {"description": "Job accepted and queued (async pipeline)"}},
)
@limiter.limit(settings.RATE_LIMIT_GENERATE)
async def generate(
    request: Request,
    req: GenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Queue a video generation job (202: o processamento acontece no worker)."""
    # Dialogo usa 2 vozes ElevenLabs na sintese: o custo e SEMPRE o pricing elevenlabs,
    # decidido aqui (server-side) — nunca por campo de custo vindo do cliente. Vale para
    # o MODO dialogo E para templates de dialogo NATIVO (dialogue_duo): o worker decide
    # a sintese por template.script.is_dialogue, entao o preco segue a mesma regra.
    template = get_template(req.template_id)
    cost_provider = (
        "elevenlabs" if (req.narration_mode == "dialogue" or template.script.is_dialogue) else req.voice_provider
    )
    base_credit_cost = get_generation_credit_cost(req.template_id, cost_provider)
    credit_cost = base_credit_cost

    # Refinos de roteiro (0,5 cada) ficam autoritativos no PostgreSQL. A parte
    # inteira entra no debito desta geracao e a fracao restante segue para a proxima.
    refine_extra = 0

    # Guardrail $: video IA (Seedance) e a operacao mais cara. Teto DIARIO por usuario, vale ate p/
    # conta admin/seed (foi o vetor do gasto de ~$6). O lock por usuario serializa get->incr (sem race).
    is_ai_video = template.media.source == "ai_video"
    cap_key = (
        f"aivideo_count:{user.id}:{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
        if is_ai_video and settings.MAX_AI_VIDEO_PER_DAY > 0
        else None
    )

    job_uuid = uuid.uuid4()
    quota_reserved = False
    legacy_projection_id: uuid.UUID | None = None
    debit_projection_id: uuid.UUID | None = None

    async with get_lock(f"generate:{user.id}"):
        _ensure_storage_ready()
        if req.custom_script is not None:
            try:
                script_path = get_job_dir(str(job_uuid)) / "script.json"
                script_path.write_text(
                    json.dumps(req.custom_script, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except Exception as exc:  # noqa: BLE001 - prove filesystem before charging
                cleanup_job_dir(str(job_uuid))
                logger.error("Falha ao preparar custom script job=%s: %s", job_uuid, exc)
                raise HTTPException(status_code=503, detail="Nao foi possivel preparar os arquivos da geracao.")

        if cap_key:
            try:
                quota_count = int(_redis.incr(cap_key))
                quota_reserved = True
                _redis.expire(cap_key, 90000)
                if quota_count > settings.MAX_AI_VIDEO_PER_DAY:
                    _release_generation_quota(cap_key, quota_reserved)
                    quota_reserved = False
                    cleanup_job_dir(str(job_uuid))
                    raise HTTPException(
                        status_code=429,
                        detail=f"Limite diário de vídeos IA atingido ({settings.MAX_AI_VIDEO_PER_DAY}/dia). Tente novamente amanhã.",
                    )
            except HTTPException:
                raise
            except Exception as exc:  # noqa: BLE001 - quota reservation precedes debit
                _release_generation_quota(cap_key, quota_reserved)
                quota_reserved = False
                cleanup_job_dir(str(job_uuid))
                logger.error("Falha ao reservar quota de geracao key=%s: %s", cap_key, exc)
                raise HTTPException(status_code=503, detail="Nao foi possivel reservar a geracao agora.")

        try:
            locked_user, legacy_projection_id = await _lock_script_refine_balance(db, user.id)
            if not locked_user.email_verified:
                raise HTTPException(status_code=403, detail=ErrorMessages.EMAIL_NOT_VERIFIED)

            refine_pending = float(locked_user.script_refine_pending or 0.0)
            refine_extra = int(refine_pending)
            credit_cost = base_credit_cost + refine_extra
            debit_values = {"credits": User.credits - credit_cost}
            await set_credit_ledger_context(
                db,
                origin="generation_debit",
                reason="generation operation reserved",
                idempotency_key=f"generation:{job_uuid}:debit",
                job_id=job_uuid,
                operation_id=job_uuid,
            )
            if refine_extra > 0:
                debit_values.update(
                    script_refine_pending=User.script_refine_pending - refine_extra,
                    script_refine_version=User.script_refine_version + 1,
                )
                debit = await db.execute(
                    update(User)
                    .where(User.id == user.id, User.email_verified.is_(True), User.credits >= credit_cost)
                    .values(**debit_values)
                    .returning(User.script_refine_pending, User.script_refine_version)
                )
                debit_row = debit.one_or_none()
                if debit_row is None:
                    raise HTTPException(status_code=402, detail=ErrorMessages.INSUFFICIENT_CREDITS)
                projection = await queue_refine_balance_projection(
                    db,
                    user_id=user.id,
                    version=int(debit_row.script_refine_version),
                    balance_after=float(debit_row.script_refine_pending),
                )
                debit_projection_id = projection.id
            else:
                debit = await db.execute(
                    update(User)
                    .where(User.id == user.id, User.email_verified.is_(True), User.credits >= credit_cost)
                    .values(**debit_values)
                )
                if debit.rowcount == 0:
                    raise HTTPException(status_code=402, detail=ErrorMessages.INSUFFICIENT_CREDITS)

            prior_generations = int(await db.scalar(select(func.count(Job.id)).where(Job.user_id == user.id)) or 0)
            generation_ordinal = "first" if prior_generations == 0 else "second" if prior_generations == 1 else "repeat"
            requested_at = datetime.now(timezone.utc)
            job = Job(
                id=job_uuid,
                user_id=user.id,
                topic=req.topic,
                style=req.style,
                duration_target=req.duration_target,
                template_id=req.template_id,
                voice_provider=req.voice_provider,
                voice_config=req.voice_config,
                credit_cost=credit_cost,
                refine_credit_cost=refine_extra,
                status="queued",
                created_at=requested_at,
            )
            db.add(job)
            dispatch = await create_dispatch(
                db,
                job_id=job_uuid,
                operation_id=job_uuid,
                kind="generation",
                payload=DispatchPayload(
                    topic=req.topic,
                    style=req.style,
                    duration_target=req.duration_target,
                    template_id=req.template_id,
                    voice_provider=req.voice_provider,
                    voice_config=req.voice_config,
                    trend_context=req.trend_context,
                    narration_mode=req.narration_mode,
                    sfx_enabled=req.sfx_enabled,
                    music_enabled=req.music_enabled,
                    custom_script=req.custom_script is not None,
                ),
                debited_credits=credit_cost,
                refine_debited=float(refine_extra),
                pending_credits_snapshot=0.0,
            )
            dispatch_id = dispatch.id
            event_properties = {
                "operation_kind": "generation",
                "credit_cost": credit_cost,
                "generation_ordinal": generation_ordinal,
            }
            await append_server_event_safely(
                db,
                event_name="generation_requested",
                user=locked_user,
                properties=event_properties,
                idempotency_key=f"job:{job_uuid}:requested",
                occurred_at=requested_at,
            )
            if generation_ordinal == "second":
                await append_server_event_safely(
                    db,
                    event_name="second_generation_requested",
                    user=locked_user,
                    properties={"credit_cost": credit_cost},
                    idempotency_key=f"user:{user.id}:second-generation",
                    occurred_at=requested_at,
                )
            if credit_cost > 0:
                await append_server_event_safely(
                    db,
                    event_name="credit_balance_changed",
                    user=locked_user,
                    properties={"reason": "generation_debit", "delta": -credit_cost},
                    idempotency_key=f"job:{job_uuid}:generation-debit",
                    occurred_at=requested_at,
                )
            await db.commit()
        except HTTPException:
            await db.rollback()
            _release_generation_quota(cap_key, quota_reserved)
            cleanup_job_dir(str(job_uuid))
            raise
        except Exception as exc:  # noqa: BLE001 - debit and queued row share one transaction
            await db.rollback()
            _release_generation_quota(cap_key, quota_reserved)
            cleanup_job_dir(str(job_uuid))
            logger.exception("Falha na transacao de geracao job=%s", job_uuid)
            raise HTTPException(status_code=503, detail="Nao foi possivel reservar a geracao agora.") from exc

        for projection_id in (legacy_projection_id, debit_projection_id):
            await _sync_refine_projection_best_effort(db, projection_id)

        record_credit_metric("debit", credit_cost)
        job_id = str(job_uuid)
        job_meta = {
            "status": "queued",
            "progress": "0",
            "current_step": "",
            "error": "",
            "detail": "",
            "template_id": req.template_id,
            "generation_broker_state": "attempting",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if req.sfx_enabled is not None:
            job_meta["sfx_enabled"] = "1" if req.sfx_enabled else "0"
        if req.music_enabled is not None:
            job_meta["music_enabled"] = "1" if req.music_enabled else "0"
        if req.narration_mode != "single":
            job_meta["narration_mode"] = req.narration_mode

        try:
            _redis.hset(f"job:{job_id}", mapping=job_meta)
            if req.custom_script is not None:
                _redis.hset(f"job:{job_id}", mapping={"custom_script": "1"})
        except Exception as exc:  # noqa: BLE001 - Redis failed before any broker call
            compensation = await _compensate_generation_dispatch(
                db,
                job_id=job_uuid,
                cap_key=cap_key,
                quota_reserved=quota_reserved,
                credit_cost=credit_cost,
                error=exc,
                dispatch_id=dispatch_id,
            )
            logger.error("Dispatch compensado job=%s user=%s: %s", job_id, user.id, exc)
            if compensation == "accepted_or_completed":
                return {"job_id": job_id, "status": "queued", "credit_cost": credit_cost}
            raise HTTPException(
                status_code=503,
                detail=(
                    "Nao foi possivel iniciar a geracao agora. Seu credito foi estornado, tente novamente em instantes."
                    if compensation in {"refunded", "already_refunded"}
                    else "Nao foi possivel iniciar a geracao agora. O estorno ficou pendente para reconciliacao."
                ),
            )

        def _publish_generation(_dispatch, *, task_id: str) -> None:
            payload = _dispatch.payload
            dispatch_pipeline(
                job_id,
                payload["topic"],
                payload["style"],
                payload["duration_target"],
                template_id=payload.get("template_id") or "stock_narration",
                voice_provider=payload.get("voice_provider") or "edge",
                voice_config=payload.get("voice_config"),
                trend_context=payload.get("trend_context"),
                narration_mode=payload.get("narration_mode") or "single",
                sfx_enabled=payload.get("sfx_enabled"),
                music_enabled=payload.get("music_enabled"),
                custom_script=bool(payload.get("custom_script")),
                dispatch_id=str(dispatch_id),
                task_id=task_id,
            )

        try:
            publish_outcome = await publish_dispatch(db, dispatch_id, send=_publish_generation)
        except Exception:  # noqa: BLE001 - durable pending outbox is reconciled with the same operation claim
            await db.rollback()
            publish_outcome = "pending"
            logger.critical("Falha apos preparar outbox de geracao job=%s", job_id, exc_info=True)

        if publish_outcome == "send_failed":
            compensation = await _compensate_generation_dispatch(
                db,
                job_id=job_uuid,
                cap_key=cap_key,
                quota_reserved=quota_reserved,
                credit_cost=credit_cost,
                error=RuntimeError("broker send failed"),
                dispatch_id=dispatch_id,
            )
            if compensation == "accepted_or_completed":
                return {"job_id": job_id, "status": "queued", "credit_cost": credit_cost}
            raise HTTPException(
                status_code=503,
                detail=(
                    "Nao foi possivel iniciar a geracao agora. Seu credito foi estornado, tente novamente em instantes."
                    if compensation in {"refunded", "already_refunded"}
                    else "Nao foi possivel iniciar a geracao agora. O estorno ficou pendente para reconciliacao."
                ),
            )

        if publish_outcome == "published":
            try:
                _redis.hset(
                    f"job:{job_id}",
                    mapping={
                        "generation_broker_accepted_at": datetime.now(timezone.utc).isoformat(),
                        "generation_broker_state": "accepted",
                    },
                )
            except Exception:  # noqa: BLE001 - the SQL outbox is the durable broker evidence
                logger.critical("Falha ao espelhar aceite do broker no Redis job=%s", job_id, exc_info=True)
        else:
            logger.warning("Geracao aguardando replay do outbox job=%s outcome=%s", job_id, publish_outcome)

        if publish_outcome in {"published", "claimed"}:
            try:
                await mark_generation_dispatched(db, job_uuid)
                await db.commit()
            except Exception as exc:  # noqa: BLE001 - accepted work must never be refunded
                await db.rollback()
                logger.critical(
                    "Broker aceitou geracao mas marker falhou job=%s user=%s; worker deve autocurar",
                    job_id,
                    user.id,
                    exc_info=True,
                )
                try:
                    await asyncio.to_thread(
                        _send_admin_alert,
                        "ClipIA - marker de dispatch da geracao falhou",
                        f"job_id={job_id} user_id={user.id} error={exc!r}. Broker aceitou; nao estornar.",
                    )
                except Exception:  # noqa: BLE001
                    logger.exception("Falha ao enviar alerta de marker job=%s", job_id)

        if is_ai_video:
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
    db: AsyncSession = Depends(get_db),
):
    """Preview do roteiro sem debitar (incluso). Anti-farming: exige saldo suficiente
    para gerar o video deste template + cap horario."""
    cost_provider = "elevenlabs" if req.narration_mode == "dialogue" else req.voice_provider
    template_cost = get_generation_credit_cost(req.template_id, cost_provider)
    locked_user, legacy_projection_id = await _lock_script_refine_balance(db, user.id)
    available_credits = int(locked_user.credits)
    await db.commit()
    await _sync_refine_projection_best_effort(db, legacy_projection_id)
    if available_credits < template_cost:
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

    await db.refresh(locked_user, attribute_names=["script_refine_pending"])
    refine_owed = float(locked_user.script_refine_pending or 0.0)
    return {
        "script": script,
        "refine_cost": float(CREDIT_TARIFFS.script_refinement),
        "refine_pending": refine_owed,
    }


@router.post(
    "/script-preview/refine",
    summary="Refinar o rascunho (0,5 crédito)",
    description="Melhora o roteiro conforme a instrução. Custa 0,5 crédito, somado ao custo da próxima geração.",
    responses={200: {"description": "Roteiro refinado"}},
)
async def script_preview_refine(
    req: ScriptRefineRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Refino = 0,5 credito acumulado no PostgreSQL e liquidado no proximo
    /generate (parte inteira; o resto carrega). Nunca um campo de custo do cliente."""
    _, legacy_projection_id = await _lock_script_refine_balance(db, user.id)
    await db.commit()
    await _sync_refine_projection_best_effort(db, legacy_projection_id)
    _script_preview_rate_limit(user.id)

    from app.services.scriptwriter import refine_script

    try:
        refined = await asyncio.to_thread(
            refine_script, req.script, req.instruction, req.duration_target, req.template_id
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("script-refine falhou user=%s: %s", user.id, e)
        raise HTTPException(status_code=502, detail="Não foi possível refinar o rascunho agora. Tente novamente.")

    # Debita os 0,5 SOMENTE com refino entregue. O incremento SQL aritmetico
    # serializa com a reserva da geracao e preserva refinamentos concorrentes.
    projection = await adjust_refine_balance(db, user.id, float(CREDIT_TARIFFS.script_refinement))
    pending = float(projection.balance_after)
    await db.commit()
    await _sync_refine_projection_best_effort(db, projection.id)
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
    operation_id = uuid.uuid4()
    await _debit_credits(
        db,
        user.id,
        cost,
        action="design_voice",
        operation_id=operation_id,
    )
    try:
        voice_id = await ElevenLabsProvider().design_voice(req.name, req.description, req.text)
    except Exception as e:  # noqa: BLE001
        await _refund_credits_safe(db, user.id, cost, "design_voice", operation_id)
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
    responses={
        200: {"description": "Video stream"},
        404: {"description": "Not found"},
        503: {"description": "Delivered artifact temporarily unavailable"},
    },
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
        if job.status in {"editable", "completed"} or job.video_url or job.completed_at:
            raise artifact_unavailable_error()
        raise not_found_error()
    if job.exported_at is None:
        exported_at = datetime.now(timezone.utc)
        job.exported_at = exported_at
        await append_server_event_safely(
            db,
            event_name="video_exported",
            user=user,
            properties={"export_ordinal": "first"},
            idempotency_key=f"job:{job.id}:first-export",
            occurred_at=exported_at,
        )
        await db.commit()
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


# Cache do catálogo ElevenLabs (compartilhado entre users; clones ficam fora, por-user)
_el_voices_cache: dict = {"at": 0.0, "voices": []}


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

    # ElevenLabs voices (if API key configured) — cache 10min: o catálogo muda raramente
    # e a chamada remota a cada request segurava a aba Voz no "Carregando vozes...".
    if settings.ELEVENLABS_API_KEY:
        now = time.monotonic()
        if _el_voices_cache["voices"] and now - _el_voices_cache["at"] < 600:
            voices.extend(_el_voices_cache["voices"])
        else:
            try:
                from app.services.elevenlabs_provider import ElevenLabsProvider

                provider = ElevenLabsProvider()
                el_voices = await provider.list_voices()
                fetched = [v.__dict__ for v in el_voices]
                _el_voices_cache.update(at=now, voices=fetched)
                voices.extend(fetched)
            except Exception as e:
                logger.warning(f"Failed to fetch ElevenLabs voices: {e}")
                # Stale-if-error: catálogo velho é melhor que aba vazia.
                voices.extend(_el_voices_cache["voices"])

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
    max_file_bytes = 10 * 1024 * 1024
    form = await parse_limited_multipart(
        request,
        max_file_bytes=max_file_bytes,
        max_total_bytes=5 * max_file_bytes + 64 * 1024,
        max_files=5,
        max_fields=2,
    )
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
        try:
            extension = declared_audio_extension(f.content_type)
            content = await read_limited_audio(
                f,
                max_bytes=max_file_bytes,
                extension=extension,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        audio_bytes.append(content)

    from app.services.elevenlabs_provider import ElevenLabsProvider

    cost = settings.CREDIT_COST_VOICE_CLONE
    operation_id = uuid.uuid4()
    await _debit_credits(
        db,
        user.id,
        cost,
        action="clone_voice",
        operation_id=operation_id,
    )
    provider = ElevenLabsProvider()
    try:
        voice_id = await provider.clone_voice(name, audio_bytes, description)
    except Exception as e:  # noqa: BLE001
        await _refund_credits_safe(db, user.id, cost, "clone_voice", operation_id)
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

    max_file_bytes = 50 * 1024 * 1024
    form = await parse_limited_multipart(
        request,
        max_file_bytes=max_file_bytes,
        max_total_bytes=max_file_bytes + 64 * 1024,
        max_files=1,
        max_fields=1,
    )
    file = form.get("file")
    if file is None:
        raise HTTPException(status_code=400, detail="Envie um arquivo de áudio")

    try:
        ext = declared_audio_extension(file.content_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    job_dir = Path(settings.STORAGE_DIR) / "jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # Stream to a temporary server-owned path, validate the signature, then publish atomically.
    upload_path = job_dir / f"upload{ext}"
    upload_temp_path = job_dir / f".upload{ext}.part"
    try:
        await write_limited_audio(
            file,
            upload_temp_path,
            max_bytes=max_file_bytes,
            extension=ext,
        )
        upload_temp_path.replace(upload_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Validate
    from app.services.custom_audio_provider import validate_audio_file

    try:
        meta = validate_audio_file(str(upload_path))
    except ValueError as e:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(e))

    # Normalize to WAV
    output_path = str(job_dir / "narration.wav")
    from app.services.custom_audio_provider import normalize_audio

    await asyncio.to_thread(normalize_audio, str(upload_path), output_path)

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

    # Load editor state from DB if exists and migrate public paths to opaque IDs.
    from app.services.music import sanitize_editor_state_assets

    editor_state = sanitize_editor_state_assets(job.editor_state)

    # Get template info
    from app.templates import get_template

    job_template_id = getattr(job, "template_id", "stock_narration")
    tmpl = get_template(job_template_id)
    from app.job_config import resolve_job_flag
    from app.services.music import auto_music_asset_id

    music_on = resolve_job_flag(_redis, job_id, "music_enabled", settings.AUTO_MUSIC_ENABLED)
    default_music_asset_id = auto_music_asset_id(job_template_id) if music_on else None

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
        music_asset_id=default_music_asset_id,
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

    job_dir = Path(settings.STORAGE_DIR) / "jobs" / job_id
    if not job_dir.exists():
        raise artifact_unavailable_error()

    await db.execute(update(Job).where(Job.id == job.id).values(editor_state=req.editor_state))
    await db.commit()

    # Sync edited state to disk for the render pipeline
    try:
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
        raise artifact_unavailable_error()

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

        cost = int(CREDIT_TARIFFS.dialogue)
        operation_id = uuid.uuid4()
        await _debit_credits(
            db,
            user.id,
            cost,
            action="regenerate_tts",
            operation_id=operation_id,
            job_id=job.id,
        )
        provider = ElevenLabsProvider()
        try:
            await provider.synthesize(
                text=narration,
                output_path=audio_path,
                voice_id=req.voice_id or "",
            )
        except Exception as e:  # noqa: BLE001
            await _refund_credits_safe(
                db,
                user.id,
                cost,
                "regenerate_tts",
                operation_id,
                job_id=job.id,
            )
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
    words_stale = False  # True = legendas podem estar dessincronizadas com o audio novo
    try:
        from app.services.transcriber import transcribe_with_timestamps

        # to_thread: transcribe (Whisper/Groq) e sincrono e travaria o event loop sem isso.
        words = await asyncio.to_thread(transcribe_with_timestamps, audio_path)
    except Exception as e:
        logger.warning(f"Whisper transcription failed, keeping old timestamps: {e}")
        words = old_words
        words_stale = True

    if not words and old_words:
        # Transcricao "bem-sucedida" mas vazia: manter as antigas e ser honesto sobre o stale.
        words = old_words
        words_stale = True

    # Save updated words
    if words:
        words_path.write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")

    return {
        "audio_url": sign_media_url(f"/storage/jobs/{job_id}/narration.wav"),
        "words": words,
        "words_stale": words_stale,
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
    # SETNX+TTL: a chamada roda 15-40s FORA de lock — dois requests paralelos do mesmo job
    # duplicariam o custo de API. TTL 90s destrava sozinho se o processo morrer no meio.
    inflight_key = f"ai_suggest:{job.id}:inflight"
    if not _redis.set(inflight_key, "1", nx=True, ex=90):
        raise HTTPException(
            status_code=429,
            detail="Já existe uma sugestão de IA em andamento para este vídeo. Aguarde ela terminar.",
        )
    try:
        raw = await asyncio.to_thread(complete_text, prompt)
    except Exception as e:  # noqa: BLE001
        logger.warning("ai_suggest LLM falhou: %s", e)
        raise HTTPException(
            status_code=502,
            detail="A IA está indisponível no momento. Tente novamente em instantes.",
        )
    finally:
        _redis.delete(inflight_key)
    raw = strip_code_fences(raw)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {"suggestions": [], "general_feedback": raw}

    async with get_lock(f"job:{job.id}:pending_credits"):
        pending_result = await db.execute(
            update(Job)
            .where(Job.id == job.id)
            .values(pending_credits=func.coalesce(Job.pending_credits, 0.0) + float(CREDIT_TARIFFS.script_refinement))
            .returning(Job.pending_credits)
        )
        pending_credits = float(pending_result.scalar_one())
        await db.commit()

    result["pending_credits"] = pending_credits
    return result


@router.post(
    "/jobs/{job_id}/render",
    summary="Render video",
    description="Starts render job.",
    responses={200: {"description": "Render queued"}, 409: {"description": "Job cannot be rendered"}},
)
async def render_video(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Re-render video with current editor state via FFmpeg+NVENC."""
    job = await get_owned_job(db, user, job_id)
    if job.status not in {"editable", "completed"}:
        raise HTTPException(status_code=409, detail="Only a delivered job can be rendered")
    if job.rerender_state in {"debited", "dispatched", "running"}:
        raise HTTPException(status_code=409, detail="A rerender is already active")
    job_uuid = job.id
    job_id = str(job_uuid)
    job_dir = Path(settings.STORAGE_DIR) / "jobs" / job_id
    if not job_dir.exists():
        raise artifact_unavailable_error()

    async with get_lock(f"render:{job_id}"):
        operation_id = uuid.uuid4()
        try:
            operation = await begin_rerender(
                db,
                job_uuid,
                user.id,
                operation_id=operation_id,
            )
            dispatch = await create_dispatch(
                db,
                job_id=job_uuid,
                operation_id=operation_id,
                kind="rerender",
                payload=DispatchPayload(rerender_cost=operation.cost),
                debited_credits=operation.cost,
                refine_debited=0.0,
                pending_credits_snapshot=operation.pending_credits,
            )
            dispatch_id = dispatch.id
            await db.commit()
        except InsufficientCredits as exc:
            await db.rollback()
            raise HTTPException(status_code=402, detail=ErrorMessages.INSUFFICIENT_CREDITS) from exc
        except InvalidJobOperation as exc:
            await db.rollback()
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        from app.worker.tasks import _update_rerender_terminal, task_rerender_video

        try:
            # Generation cancellation is a separate operation. Only a valid,
            # persisted rerender may clear a stale legacy generation flag. This
            # Redis mutation is still pre-broker, so a failure must compensate
            # the already-persisted rerender debit below.
            _redis.delete(f"job:{job_id}:cancelled")
            _redis.hset(
                f"job:{job_id}",
                mapping={
                    "status": "rendering",
                    "progress": 0.0,
                    "current_step": "queued",
                    "detail": "Re-render enfileirado...",
                    "rerender_cost": operation.cost,
                    "rerender_operation_id": str(operation_id),
                    "rerender_broker_state": "attempting",
                },
            )
        except Exception as exc:  # noqa: BLE001 - Redis failed before any broker call
            compensation = await _compensate_rerender_dispatch(
                db,
                job_id=job_uuid,
                operation_id=operation_id,
                dispatch_id=dispatch_id,
            )
            if compensation == "accepted_or_completed":
                return {"status": "rendering", "message": "Re-render iniciado com edicoes atuais."}
            if compensation in {"refunded", "already_refunded", "refund_pending"}:
                try:
                    _update_rerender_terminal(
                        job_id,
                        str(operation_id),
                        status="completed" if compensation != "refund_pending" else "refund_pending",
                        error="" if compensation != "refund_pending" else "Estorno persistente pendente.",
                        detail=(
                            "Re-render nao pode ser enfileirado; credito estornado."
                            if compensation != "refund_pending"
                            else "Re-render nao foi enfileirado; estorno pendente para reconciliacao."
                        ),
                        broker_state="failed",
                    )
                except Exception:  # noqa: BLE001 - DB is authoritative
                    logger.exception("Falha ao publicar compensation Redis rerender job=%s", job_id)
            logger.error("Dispatch de rerender compensado job=%s op=%s: %s", job_id, operation_id, exc)
            raise HTTPException(
                status_code=503,
                detail=(
                    "Nao foi possivel iniciar o re-render agora. Seu credito foi estornado, tente novamente."
                    if compensation in {"refunded", "already_refunded"}
                    else "Nao foi possivel iniciar o re-render agora. O estorno ficou pendente para reconciliacao."
                ),
            )

        def _publish_rerender(_dispatch, *, task_id: str) -> None:
            if hasattr(task_rerender_video, "apply_async"):
                task_rerender_video.apply_async(
                    args=(job_id, str(operation_id), str(_dispatch.id), task_id),
                    task_id=task_id,
                )
            else:  # compatibility for pre-outbox queued-task adapters during rolling tests
                task_rerender_video.delay(job_id, str(operation_id))

        try:
            publish_outcome = await publish_dispatch(db, dispatch_id, send=_publish_rerender)
        except Exception:  # noqa: BLE001 - durable pending outbox will be replayed
            await db.rollback()
            publish_outcome = "pending"
            logger.critical("Falha apos preparar outbox do rerender job=%s op=%s", job_id, operation_id, exc_info=True)

        if publish_outcome == "send_failed":
            compensation = await _compensate_rerender_dispatch(
                db,
                job_id=job_uuid,
                operation_id=operation_id,
                dispatch_id=dispatch_id,
            )
            if compensation == "accepted_or_completed":
                return {"status": "rendering", "message": "Re-render iniciado com edicoes atuais."}
            if compensation in {"refunded", "already_refunded", "refund_pending"}:
                try:
                    _update_rerender_terminal(
                        job_id,
                        str(operation_id),
                        status="completed" if compensation != "refund_pending" else "refund_pending",
                        error="" if compensation != "refund_pending" else "Estorno persistente pendente.",
                        detail=(
                            "Re-render nao pode ser enfileirado; credito estornado."
                            if compensation != "refund_pending"
                            else "Re-render nao foi enfileirado; estorno pendente para reconciliacao."
                        ),
                        broker_state="failed",
                    )
                except Exception:  # noqa: BLE001 - DB remains authoritative
                    logger.exception("Falha ao publicar compensation Redis rerender job=%s", job_id)
            raise HTTPException(
                status_code=503,
                detail=(
                    "Nao foi possivel iniciar o re-render agora. Seu credito foi estornado, tente novamente."
                    if compensation in {"refunded", "already_refunded"}
                    else "Nao foi possivel iniciar o re-render agora. O estorno ficou pendente para reconciliacao."
                ),
            )

        if publish_outcome == "published":
            try:
                _redis.hset(
                    f"job:{job_id}",
                    mapping={
                        "rerender_broker_accepted_at": datetime.now(timezone.utc).isoformat(),
                        "rerender_broker_accepted_operation_id": str(operation_id),
                        "rerender_broker_state": "accepted",
                    },
                )
            except Exception:  # noqa: BLE001 - SQL outbox is authoritative
                logger.critical(
                    "Falha ao espelhar aceite Redis job=%s op=%s",
                    job_id,
                    operation_id,
                    exc_info=True,
                )
        else:
            logger.warning(
                "Rerender aguardando replay do outbox job=%s op=%s outcome=%s",
                job_id,
                operation_id,
                publish_outcome,
            )

        if publish_outcome in {"published", "claimed"}:
            try:
                if await mark_rerender_dispatched(db, job_uuid, operation_id):
                    await db.commit()
            except Exception as exc:  # noqa: BLE001 - broker accepted; worker claim self-heals marker
                await db.rollback()
                logger.critical(
                    "Broker aceitou rerender mas marker falhou job=%s op=%s; worker deve autocurar",
                    job_id,
                    operation_id,
                    exc_info=True,
                )
                try:
                    await asyncio.to_thread(
                        _send_admin_alert,
                        "ClipIA - marker de dispatch do rerender falhou",
                        f"job_id={job_id} operation_id={operation_id} error={exc!r}. Nao estornar.",
                    )
                except Exception:  # noqa: BLE001
                    logger.exception("Falha ao enviar alerta de marker do rerender job=%s", job_id)

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
        # commit=False: debito + reset do job na MESMA transacao (erro entre eles nao
        # deixa o credito cobrado com o editor_state intacto).
        await _debit_credits(
            db,
            user.id,
            1,
            commit=False,
            action="job_reset",
            operation_id=uuid.uuid4(),
            job_id=job.id,
        )
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
        # O ExportPanel abre com o pending_credits da composition (carregada no mount do
        # editor) — ai-suggest/render mudam o valor no servidor e o banner mentia. O job
        # ja esta carregado aqui (get_owned_job), entao expor o valor fresco e gratis.
        "pending_credits": float(job.pending_credits or 0.0),
    }


@router.post(
    "/jobs/{job_id}/cancel",
    summary="Cancel job",
    description="Cancels an ongoing job.",
    responses={200: {"description": "Cancel initiated"}, 409: {"description": "Job cannot be cancelled"}},
)
async def cancel_job(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Persist cancellation before signalling workers through Redis."""
    job = await get_owned_job(db, user, job_id)
    job_id = str(job.id)

    try:
        await request_generation_cancel(db, job.id, user.id)
    except InvalidJobOperation as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await db.commit()

    _redis.set(f"job:{job_id}:cancelled", "true", ex=24 * 60 * 60)
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
            rows = q.all()

            def _live_statuses() -> dict:
                return {str(jid): _redis.hgetall(f"job:{jid}") for jid, _ in rows}

            live_map = await asyncio.to_thread(_live_statuses)  # ate 200 hgetall fora do event loop
            live_queue = []
            for jid, jcreated in rows:
                live = live_map.get(str(jid))
                live_status = live.get("status") if live else None
                # sem hash = ainda nem comecou (na fila); ativos seguem na conta
                if live_status in (None, "", "queued", "processing", "rendering"):
                    live_queue.append(jcreated)
        return sum(1 for other in live_queue if other and other < created_at)

    def _collect_live_sync() -> dict[str, dict]:
        # Redis sync + ate 3 stat() por job rodavam soltos no handler async, bloqueando
        # o event loop ~50-150ms a cada poll do dashboard. Uma passada em thread coleta tudo.
        output_dir = Path(settings.STORAGE_DIR) / "output"
        jobs_dir = Path(settings.STORAGE_DIR) / "jobs"
        collected: dict[str, dict] = {}
        for j in jobs:
            jid = str(j.id)
            collected[jid] = {
                "redis": _redis.hgetall(f"job:{jid}"),
                "has_video": bool(j.video_url) or (output_dir / f"{jid}.mp4").exists(),
                "has_script": (jobs_dir / jid / "script.json").exists(),
                "has_thumb": (output_dir / f"{jid}.jpg").exists(),
            }
        return collected

    live_by_job = await asyncio.to_thread(_collect_live_sync)

    items = []
    for j in jobs:
        live = live_by_job[str(j.id)]
        # Redis has the real-time status; DB may be stale
        redis_data = live["redis"]
        status = redis_data.get("status", j.status) if redis_data else j.status
        has_video = live["has_video"]
        # Em estado ativo o arquivo em output/ pode ser a versao ANTIGA (re-render em
        # andamento): esconder o download fecha pelo dashboard a mesma corrida que o
        # editor fecha via get_job (baixar video pre-edicao).
        downloadable = has_video and status not in {"queued", "processing", "rendering", "cancelling"}
        # Treat completed jobs as editable if they have composition files
        if status == "completed" and live["has_script"]:
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
                "thumbnail_url": (f"/api/v1/jobs/{j.id}/thumbnail" if live["has_thumb"] else None),
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
    """Estimativa operacional baseada na telemetria disponível no finalize.

    Jobs sem telemetry ficam de fora e ``api_cost_usd_est`` não substitui
    faturas, câmbio, impostos, storage, tráfego ou suporte.
    """
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

    return {
        "basis": "estimate",
        "telemetry_jobs": len(items),
        "limitations": "Exclui jobs sem telemetria e nao representa COGS real reconciliado com faturas.",
        "jobs": items,
        "by_template": by_template,
    }


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

    canonical_state_sql = canonical_payment_state_expression(
        CreditPurchase.status,
        CreditPurchase.payment_state,
    )
    purchases_result = await db.execute(
        select(CreditPurchase, canonical_state_sql.label("canonical_state")).where(
            or_(
                CreditPurchase.created_at >= window_start,
                CreditPurchase.paid_at >= window_start,
                CreditPurchase.refunded_at >= window_start,
            )
        )
    )
    purchase_rows = list(purchases_result.all())
    purchases_in_range = [row[0] for row in purchase_rows]
    purchase_states = {row[0].id: row[1] for row in purchase_rows}

    jobs_result = await db.execute(select(Job).where(Job.created_at >= window_start))
    jobs_in_range = list(jobs_result.scalars().all())

    dispatches_result = await db.execute(select(JobDispatch).where(JobDispatch.created_at >= window_start))
    dispatches_in_range = list(dispatches_result.scalars().all())

    analytics_result = await db.execute(select(AnalyticsEvent).where(AnalyticsEvent.occurred_at >= window_start))
    analytics_events = list(analytics_result.scalars().all())

    coverage_window_start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=13)
    coverage_window_end = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    coverage_result = await db.execute(
        select(AnalyticsEvent.occurred_at).where(
            AnalyticsEvent.authority == "client",
            AnalyticsEvent.event_name == "landing_viewed",
            AnalyticsEvent.occurred_at >= coverage_window_start,
            AnalyticsEvent.occurred_at < coverage_window_end,
        )
    )
    coverage_occurred_at = list(coverage_result.scalars().all())

    def in_window(value: datetime | None) -> bool:
        utc_value = _coerce_utc(value)
        return utc_value is not None and utc_value >= window_start

    created_purchases = [purchase for purchase in purchases_in_range if in_window(purchase.created_at)]
    gross_paid_purchases = [
        purchase
        for purchase in purchases_in_range
        if purchase_states[purchase.id] in {"paid", "refunded"} and in_window(purchase.paid_at)
    ]
    pending_purchases = [purchase for purchase in created_purchases if purchase_states[purchase.id] == "pending"]
    refunded_purchases = [
        purchase
        for purchase in purchases_in_range
        if purchase_states[purchase.id] == "refunded" and in_window(purchase.refunded_at)
    ]
    invalid_purchases = [
        purchase
        for purchase in purchases_in_range
        if purchase_states[purchase.id] == "__invalid__"
        or (purchase_states[purchase.id] == "paid" and purchase.paid_at is None)
        or (purchase_states[purchase.id] == "refunded" and purchase.refunded_at is None)
    ]

    approved_user_ids_result = await db.execute(
        select(CreditPurchase.user_id).where(canonical_state_sql == "paid").distinct()
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

    for purchase in gross_paid_purchases:
        bucket = _bucket_key(purchase.paid_at)
        if bucket:
            revenue_by_day[bucket] += purchase.price_brl / 100
            approved_orders_by_day[bucket] += 1

    relevant_purchase_ids = {
        purchase.id for purchase in [*created_purchases, *gross_paid_purchases, *refunded_purchases]
    }
    for purchase in purchases_in_range:
        if purchase.id not in relevant_purchase_ids:
            continue
        mix = package_mix.setdefault(
            purchase.package_name,
            {
                "package_name": purchase.package_name,
                "orders": 0,
                "checkouts": 0,
                "pending_orders": 0,
                "paid_orders": 0,
                "refunded_orders": 0,
                "pending_checkout_value_brl": 0.0,
                "paid_gross_revenue_brl": 0.0,
                "refunded_value_brl": 0.0,
                "net_revenue_brl": 0.0,
                "approved_revenue_brl": 0.0,
                "credits_sold": 0,
            },
        )
        if purchase in created_purchases:
            mix["orders"] = int(mix["orders"]) + 1
            mix["checkouts"] = int(mix["checkouts"]) + 1
        if purchase in pending_purchases:
            mix["pending_orders"] = int(mix["pending_orders"]) + 1
            mix["pending_checkout_value_brl"] = _round2(
                float(mix["pending_checkout_value_brl"]) + (purchase.price_brl / 100)
            )
        if purchase in gross_paid_purchases:
            paid_value = _round2(float(mix["paid_gross_revenue_brl"]) + (purchase.price_brl / 100))
            mix["paid_orders"] = int(mix["paid_orders"]) + 1
            mix["paid_gross_revenue_brl"] = paid_value
            mix["approved_revenue_brl"] = paid_value
            mix["credits_sold"] = int(mix["credits_sold"]) + purchase.credits_amount + purchase.bonus_credits
        if purchase in refunded_purchases:
            mix["refunded_orders"] = int(mix["refunded_orders"]) + 1
            mix["refunded_value_brl"] = _round2(float(mix["refunded_value_brl"]) + (purchase.price_brl / 100))

    for mix in package_mix.values():
        mix["net_revenue_brl"] = _round2(float(mix["paid_gross_revenue_brl"]) - float(mix["refunded_value_brl"]))

    for job in jobs_in_range:
        bucket = _bucket_key(job.created_at)
        if bucket:
            jobs_by_day[bucket] += 1

    delivered_dispatches = [dispatch for dispatch in dispatches_in_range if dispatch.state == "completed"]
    cancelled_dispatches = [dispatch for dispatch in dispatches_in_range if dispatch.state == "cancelled"]
    active_dispatches = [
        dispatch for dispatch in dispatches_in_range if dispatch.state in {"pending", "published", "claimed"}
    ]
    terminal_dispatches = [*delivered_dispatches, *cancelled_dispatches]
    operation_success_rate = (
        _round2((len(delivered_dispatches) / len(terminal_dispatches)) * 100) if terminal_dispatches else 0.0
    )

    avg_pending_credits = (
        _round2(sum(pending_credits_jobs) / len(pending_credits_jobs)) if pending_credits_jobs else 0.0
    )

    storage_stats = await _build_storage_stats(db)

    paid_gross_revenue_brl = _round2(sum(purchase.price_brl for purchase in gross_paid_purchases) / 100)
    pending_revenue_brl = _round2(sum(purchase.price_brl for purchase in pending_purchases) / 100)
    refunded_value_brl = _round2(sum(purchase.price_brl for purchase in refunded_purchases) / 100)
    net_revenue_brl = _round2(paid_gross_revenue_brl - refunded_value_brl)
    approved_orders = len(gross_paid_purchases)
    average_ticket_brl = _round2(paid_gross_revenue_brl / approved_orders) if approved_orders else 0.0
    verified_users = sum(1 for user in users_in_range if user.email_verified)
    registered = len(users_in_range)
    cohort_user_ids = {str(user.id) for user in users_in_range}
    paying_users = len(cohort_user_ids & approved_user_ids)

    session_user_candidates: dict[str, set[str]] = defaultdict(set)
    for event in analytics_events:
        if event.anonymous_session_id is not None and event.user_id is not None:
            session_user_candidates[str(event.anonymous_session_id)].add(str(event.user_id))
    session_user_ids = {
        session_id: next(iter(user_ids))
        for session_id, user_ids in session_user_candidates.items()
        if len(user_ids) == 1
    }

    def analytics_identity(event: AnalyticsEvent) -> str | None:
        if event.user_id is not None:
            return f"user:{event.user_id}"
        if event.anonymous_session_id is None:
            return None
        session_id = str(event.anonymous_session_id)
        linked_user_id = session_user_ids.get(session_id)
        return f"user:{linked_user_id}" if linked_user_id else f"session:{session_id}"

    events_by_identity: dict[str, list[tuple[datetime, datetime, str]]] = defaultdict(list)
    for event in analytics_events:
        identity = analytics_identity(event)
        occurred_at = _coerce_utc(event.occurred_at)
        if identity is None or occurred_at is None:
            continue
        received_at = _coerce_utc(event.received_at) or occurred_at
        events_by_identity[identity].append((occurred_at, received_at, event.event_name))

    StageCursor = tuple[datetime, datetime]
    StageIdentities = dict[str, StageCursor]

    def next_stage_identities(
        prior_stage: StageIdentities | None,
        event_name: str,
    ) -> StageIdentities:
        reached: StageIdentities = {}
        candidates = prior_stage.keys() if prior_stage is not None else events_by_identity.keys()
        for identity in candidates:
            prior_cursor = prior_stage.get(identity) if prior_stage is not None else None
            for occurred_at, received_at, candidate_name in sorted(events_by_identity[identity]):
                cursor = (occurred_at, received_at)
                if candidate_name == event_name and (prior_cursor is None or cursor >= prior_cursor):
                    reached[identity] = cursor
                    break
        return reached

    def ordered_stage_identities(sequence: tuple[str, ...]) -> dict[str, StageIdentities]:
        reached: dict[str, StageIdentities] = {}
        prior_stage: StageIdentities | None = None
        for stage in sequence:
            prior_stage = next_stage_identities(prior_stage, stage)
            reached[stage] = prior_stage
        return reached

    acquisition_sequence = (
        "landing_viewed",
        "hero_cta_clicked",
        "user_registered",
        "email_verified",
    )
    funnel_stages = ordered_stage_identities(acquisition_sequence)
    verified_identities = funnel_stages["email_verified"]
    first_generation_identities = next_stage_identities(verified_identities, "generation_requested")
    exported_identities = next_stage_identities(first_generation_identities, "video_exported")
    checkout_identities = next_stage_identities(verified_identities, "checkout_started")
    paying_identities = next_stage_identities(checkout_identities, "payment_completed")
    second_generation_identities = next_stage_identities(
        first_generation_identities,
        "second_generation_requested",
    )
    post_export_checkout_identities = next_stage_identities(exported_identities, "checkout_started")
    post_export_paying_identities = next_stage_identities(
        post_export_checkout_identities,
        "payment_completed",
    )

    signup_stages = ordered_stage_identities(("user_registered", "email_verified"))
    signup_verified_identities = signup_stages["email_verified"]
    signup_first_generation_identities = next_stage_identities(
        signup_verified_identities,
        "generation_requested",
    )
    signup_exported_identities = next_stage_identities(
        signup_first_generation_identities,
        "video_exported",
    )
    signup_checkout_identities = next_stage_identities(signup_verified_identities, "checkout_started")
    signup_paying_identities = next_stage_identities(signup_checkout_identities, "payment_completed")
    signup_second_generation_identities = next_stage_identities(
        signup_first_generation_identities,
        "second_generation_requested",
    )

    def user_ids_at(stage_identities: StageIdentities) -> set[str]:
        return {identity.removeprefix("user:") for identity in stage_identities if identity.startswith("user:")}

    signup_verified_user_ids = user_ids_at(signup_verified_identities)
    signup_first_generation_user_ids = user_ids_at(signup_first_generation_identities)
    signup_exported_user_ids = user_ids_at(signup_exported_identities)
    signup_checkout_user_ids = user_ids_at(signup_checkout_identities)
    signup_paying_user_ids = user_ids_at(signup_paying_identities)
    signup_second_generation_user_ids = user_ids_at(signup_second_generation_identities)

    device_by_user: dict[str, tuple[datetime, str]] = {}
    for event in analytics_events:
        identity = analytics_identity(event)
        if not identity or not identity.startswith("user:") or event.device_class == "unknown":
            continue
        user_id = identity.removeprefix("user:")
        if user_id not in cohort_user_ids:
            continue
        occurred_at = _coerce_utc(event.occurred_at) or now
        current = device_by_user.get(user_id)
        if current is None or occurred_at < current[0]:
            device_by_user[user_id] = (occurred_at, event.device_class)

    def safe_cohort_token(value: str | None, fallback: str) -> str:
        normalized = value.strip().lower() if value else ""
        if normalized and len(normalized) <= 100 and all(char.isalnum() or char in "._-" for char in normalized):
            return normalized
        return fallback

    def user_niche(user: User) -> str:
        campaign = safe_cohort_token(user.utm_campaign, "")
        if campaign.startswith("nicho-"):
            niche = campaign.removeprefix("nicho-")
            if niche in _ANALYTICS_NICHES:
                return niche
        return "unknown"

    def weekly_key(user: User) -> str:
        created_at = _coerce_utc(user.created_at) or now
        return (created_at.date() - timedelta(days=created_at.weekday())).isoformat()

    def cohort_metrics(key: str, user_ids: set[str]) -> dict[str, int | float | str]:
        cohort_registered = len(user_ids)
        cohort_verified = len(user_ids & signup_verified_user_ids)
        cohort_first = len(user_ids & signup_first_generation_user_ids)
        cohort_exported = len(user_ids & signup_exported_user_ids)
        cohort_checkout = len(user_ids & signup_checkout_user_ids)
        cohort_paying = len(user_ids & signup_paying_user_ids)
        cohort_second = len(user_ids & signup_second_generation_user_ids)
        return {
            "key": key,
            "registered": cohort_registered,
            "verified": cohort_verified,
            "first_generation": cohort_first,
            "exported": cohort_exported,
            "checkout_started": cohort_checkout,
            "paying": cohort_paying,
            "second_generation": cohort_second,
            "verification_rate": _round2((cohort_verified / cohort_registered) * 100) if cohort_registered else 0.0,
            "activation_rate": _round2((cohort_first / cohort_verified) * 100) if cohort_verified else 0.0,
            "payer_conversion_rate": _round2((cohort_paying / cohort_registered) * 100) if cohort_registered else 0.0,
        }

    def grouped_cohorts(group_key) -> list[dict[str, int | float | str]]:
        groups: dict[str, set[str]] = defaultdict(set)
        for user in users_in_range:
            groups[group_key(user)].add(str(user.id))
        return [cohort_metrics(key, groups[key]) for key in sorted(groups)]

    collection_flags_aligned = settings.ANALYTICS_ENABLED and settings.ANALYTICS_FRONTEND_ENABLED
    client_collection_dates = {
        occurred_at.date() for value in coverage_occurred_at if (occurred_at := _coerce_utc(value)) is not None
    }
    baseline_days = 0
    if collection_flags_aligned:
        cursor = now.date()
        while cursor in client_collection_dates:
            baseline_days += 1
            cursor -= timedelta(days=1)
    baseline_start = now.date() - timedelta(days=baseline_days - 1) if baseline_days else None

    visited_identities = funnel_stages["landing_viewed"]
    cta_identities = funnel_stages["hero_cta_clicked"]
    registered_identities = funnel_stages["user_registered"]

    return {
        "range": range,
        "window_start": window_start.date().isoformat(),
        "window_end": now.date().isoformat(),
        "summary": {
            "paid_gross_revenue_brl": paid_gross_revenue_brl,
            "pending_checkout_value_brl": pending_revenue_brl,
            "refunded_value_brl": refunded_value_brl,
            "refund_adjustment_brl": -refunded_value_brl,
            "net_revenue_brl": net_revenue_brl,
            "approved_revenue_brl": paid_gross_revenue_brl,
            "pending_revenue_brl": pending_revenue_brl,
            "approved_orders": approved_orders,
            "pending_orders": len(pending_purchases),
            "refunded_orders": len(refunded_purchases),
            "invalid_purchase_rows": len(invalid_purchases),
            "average_ticket_brl": average_ticket_brl,
            "new_users": registered,
            "verified_users": verified_users,
            "paying_users": paying_users,
            "active_jobs": int(current_job_statuses["queued"] + current_job_statuses["processing"]),
            "credits_sold": int(
                sum(purchase.credits_amount + purchase.bonus_credits for purchase in gross_paid_purchases)
            ),
            "credits_consumed": int(sum(dispatch.debited_credits for dispatch in delivered_dispatches)),
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
            "visited": len(visited_identities),
            "cta_clicked": len(cta_identities),
            "registered": len(registered_identities),
            "verified": len(verified_identities),
            "first_generation": len(first_generation_identities),
            "exported": len(exported_identities),
            "checkout_started": len(checkout_identities),
            "paying": len(paying_identities),
            "second_generation": len(second_generation_identities),
            "verification_rate": _round2((len(verified_identities) / len(registered_identities)) * 100)
            if registered_identities
            else 0.0,
            "payer_conversion_rate": _round2((len(paying_identities) / len(registered_identities)) * 100)
            if registered_identities
            else 0.0,
            "cta_registration_rate": _round2((len(registered_identities) / len(cta_identities)) * 100)
            if cta_identities
            else 0.0,
            "activation_rate": _round2((len(first_generation_identities) / len(verified_identities)) * 100)
            if verified_identities
            else 0.0,
            "export_payment_rate": _round2((len(post_export_paying_identities) / len(exported_identities)) * 100)
            if exported_identities
            else 0.0,
            "second_generation_rate": _round2(
                (len(second_generation_identities) / len(first_generation_identities)) * 100
            )
            if first_generation_identities
            else 0.0,
            "analytics_enabled": settings.ANALYTICS_ENABLED,
            "analytics_frontend_enabled": settings.ANALYTICS_FRONTEND_ENABLED,
            "collection_flags_aligned": collection_flags_aligned,
            "baseline_started_at": baseline_start.isoformat() if baseline_start else None,
            "baseline_days": baseline_days,
            "onboarding_gate_ready": collection_flags_aligned and baseline_days >= 14,
        },
        "cohorts": {
            "weekly": grouped_cohorts(weekly_key),
            "source": grouped_cohorts(lambda user: safe_cohort_token(user.utm_source, "direct")),
            "niche": grouped_cohorts(user_niche),
            "device": grouped_cohorts(lambda user: device_by_user.get(str(user.id), (now, "unknown"))[1]),
        },
        "operations": {
            "queued_jobs": int(current_job_statuses["queued"]),
            "processing_jobs": int(current_job_statuses["processing"]),
            "completed_jobs": int(current_job_statuses["completed"]),
            "failed_jobs": int(current_job_statuses["failed"]),
            "success_rate": operation_success_rate,
            "operation_success_rate": operation_success_rate,
            "delivered_operations": len(delivered_dispatches),
            "delivered_generation_operations": sum(
                1 for dispatch in delivered_dispatches if dispatch.kind == "generation"
            ),
            "delivered_rerender_operations": sum(1 for dispatch in delivered_dispatches if dispatch.kind == "rerender"),
            "cancelled_generation_operations": sum(
                1 for dispatch in cancelled_dispatches if dispatch.kind == "generation"
            ),
            "cancelled_rerender_operations": sum(1 for dispatch in cancelled_dispatches if dispatch.kind == "rerender"),
            "active_generation_operations": sum(1 for dispatch in active_dispatches if dispatch.kind == "generation"),
            "active_rerender_operations": sum(1 for dispatch in active_dispatches if dispatch.kind == "rerender"),
            "avg_pending_credits": avg_pending_credits,
            **storage_stats,
        },
        "package_mix": sorted(
            package_mix.values(),
            key=lambda item: (float(item["net_revenue_brl"]), int(item["orders"])),
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
                    "status": canonical_payment_state_or_invalid(purchase.status, purchase.payment_state),
                    "created_at": purchase.created_at.isoformat() if purchase.created_at else None,
                    "paid_at": purchase.paid_at.isoformat() if purchase.paid_at else None,
                    "refunded_at": purchase.refunded_at.isoformat() if purchase.refunded_at else None,
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
            .where(
                CreditPurchase.user_id.in_([u.id for u in users]),
                canonical_payment_state_expression(
                    CreditPurchase.status,
                    CreditPurchase.payment_state,
                )
                == "paid",
            )
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
        requested_status = "paid" if status.strip().lower() == "approved" else status.strip().lower()
        state_filter = (
            canonical_payment_state_expression(CreditPurchase.status, CreditPurchase.payment_state) == requested_status
        )
        stmt = stmt.where(state_filter)
        count_stmt = count_stmt.where(state_filter)

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
                "status": canonical_payment_state_or_invalid(p.status, p.payment_state),
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "paid_at": p.paid_at.isoformat() if p.paid_at else None,
                "refunded_at": p.refunded_at.isoformat() if p.refunded_at else None,
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
    target = await db.scalar(select(User).where(User.id == validate_uuid(user_id)).with_for_update())
    if not target:
        raise not_found_error()

    previous = target.credits
    if previous + req.delta < 0:
        await db.rollback()
        raise HTTPException(status_code=409, detail="insufficient_credits")

    adjustment_id = uuid.uuid4()
    await set_credit_ledger_context(
        db,
        origin="admin_adjustment",
        reason=req.reason.strip(),
        idempotency_key=f"admin-adjustment:{adjustment_id}",
        operation_id=adjustment_id,
    )
    balance_result = await db.execute(
        update(User).where(User.id == target.id).values(credits=User.credits + req.delta).returning(User.credits)
    )
    new_balance = int(balance_result.scalar_one())
    db.add(
        CreditAdjustment(
            id=adjustment_id,
            admin_user_id=admin_user.id,
            target_user_id=target.id,
            delta=req.delta,
            reason=req.reason.strip(),
            previous_balance=previous,
            new_balance=new_balance,
        )
    )
    applied = new_balance - previous
    if applied:
        await append_server_event_safely(
            db,
            event_name="credit_balance_changed",
            user=target,
            properties={"reason": "admin", "delta": applied},
            idempotency_key=f"admin-adjustment:{adjustment_id}:credit",
            occurred_at=datetime.now(timezone.utc),
        )
    await db.commit()

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
