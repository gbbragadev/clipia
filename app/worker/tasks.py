import asyncio
import json
import logging
import shutil
import smtplib
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from pathlib import Path

from celery.exceptions import SoftTimeLimitExceeded

from app.config import settings
from app.redis_pool import get_redis
from app.services.compositor import compose_short
from app.services.image_provider import ModerationBlockedError, OpenAIImageProvider
from app.services.media import download_media, order_candidates, search_media_for_scene
from app.services.outro import append_outro
from app.services.scriptwriter import generate_script
from app.services.transcriber import transcribe_with_timestamps
from app.services.tts import synthesize_narration
from app.templates import get_template
from app.utils.files import bytes_to_gb, cleanup_job_dir, get_job_dir, get_output_dir, remove_path
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)

_redis = get_redis()


def _write_thumbnail(video_path: str, thumb_path: str) -> None:
    """Poster do card no dashboard: 1 frame em ~1.5s (depois do fade de abertura).

    Falha de thumbnail NUNCA falha o job — o card tem fallback de gradiente.
    """
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                "1.5",
                "-i",
                video_path,
                "-frames:v",
                "1",
                "-vf",
                "scale=360:-2",
                "-q:v",
                "4",
                thumb_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    except Exception as e:  # noqa: BLE001 — best-effort por design
        logger.warning(f"Thumbnail nao gerado para {video_path}: {e}")


def _read_json_file(path: Path):
    """Read JSON tolerating legacy non-UTF-8 files (older worker wrote cp1252)."""
    raw = path.read_bytes()
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return json.loads(raw.decode(enc))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    return json.loads(raw.decode("utf-8", errors="replace"))


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
        # Heartbeat do watchdog: time limits do Celery sao no-op no pool solo
        # (Windows); um job sem update ha mais que o limiar do step esta travado.
        "updated_at": datetime.now(timezone.utc).isoformat(),
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

        from app.db.engine import worker_session as async_session  # NullPool: seguro com asyncio.run() por task
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


@celery_app.task(name="generate_images", bind=True, soft_time_limit=180, time_limit=210)
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
            script = _read_json_file(script_path)

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


@celery_app.task(name="generate_videos", bind=True, soft_time_limit=720, time_limit=780)
def task_generate_videos(self, data: dict, job_id: str, template_id: str) -> dict:
    try:
        if _check_cancelled(job_id):
            return data

        template = get_template(template_id)
        if template.media.source != "ai_video":
            return data

        script = data.get("script") or _read_json_file(get_job_dir(job_id) / "script.json")
        scenes = script.get("scenes", [])
        if not scenes:
            raise ValueError("Script sem cenas")

        _update_job(job_id, "processing", "generating_videos", 0.15, detail=f"Gerando {len(scenes)} clipes IA...")

        suffix = template.media.style_suffix
        prompts = []
        for i, scene in enumerate(scenes):
            hint = scene.get("visual_hint", "").strip()
            if not hint:
                raise ValueError(f"cena {i+1} sem visual_hint")
            prompts.append(f"{hint}, {suffix}" if suffix else hint)

        from app.services.video_gen_provider import generate_scenes

        videos_dir = get_job_dir(job_id) / "videos"
        paths = asyncio.run(generate_scenes(prompts, str(videos_dir)))
        data["video_paths"] = paths
        _update_job(job_id, "processing", "generating_videos", 0.30, detail=f"{len(paths)} clipes IA prontos.")
        return data

    except SoftTimeLimitExceeded:
        _handle_soft_timeout(job_id, "generate_videos")
        raise
    except Exception as e:
        _fail_job(job_id, f"Falha ao gerar videos IA: {e}")
        raise


def dispatch_pipeline(
    job_id: str,
    topic: str,
    style: str,
    duration_target: int,
    template_id: str = "stock_narration",
    voice_provider: str = "edge",
    voice_config: dict | None = None,
    trend_context: str | None = None,
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
        task_generate_script.s(job_id, topic, style, duration_target, template_id, trend_context),
        task_generate_images.s(job_id, template_id),
        task_generate_videos.s(job_id, template_id),
        task_synthesize_audio.s(job_id, template_id),
        task_transcribe_audio.s(job_id),
        task_fetch_media.s(job_id, template_id),
        task_compose_video.s(job_id, template_id),
        task_finalize.s(job_id),
    )
    pipeline.apply_async()


async def _cleanup_old_jobs_async() -> dict[str, int]:
    from sqlalchemy import select

    from app.db.engine import worker_session as async_session  # NullPool: seguro com asyncio.run() por task
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

    from app.db.engine import worker_session as async_session  # NullPool: seguro com asyncio.run() por task
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


ORPHAN_QUEUED_CUTOFF_HOURS = 6
ORPHAN_QUEUED_ERROR = f"Job órfão: chain aparentemente abandonada (sem progresso há >{ORPHAN_QUEUED_CUTOFF_HOURS}h)"


async def _find_orphan_queued_jobs_async() -> list[str]:
    """Retorna os IDs de jobs em ``queued`` (Postgres) ha mais de 6h (chain provavelmente morta).

    ATENCAO: o Postgres fica "queued" durante TODO o processamento (o status vivo anda so
    no Redis; o Postgres muda no finalize/falha). Alem disso a fila e solo/concurrency=1:
    com lote de temas, um job pode esperar horas em queued LEGITIMAMENTE. Por isso o cutoff
    e 6h — o caso comum de travamento (processing estagnado) e coberto pelo watchdog de
    heartbeat (:func:`_watchdog_pass`), que age em minutos.
    """
    from sqlalchemy import select

    from app.db.engine import worker_session as async_session  # NullPool: seguro com asyncio.run() por task
    from app.db.models import Job

    cutoff = datetime.now(timezone.utc) - timedelta(hours=ORPHAN_QUEUED_CUTOFF_HOURS)
    async with async_session() as session:
        result = await session.execute(select(Job.id).where(Job.status == "queued", Job.created_at <= cutoff))
        return [str(jid) for jid in result.scalars().all()]


def _reap_orphan_queued_jobs() -> int:
    """Marca jobs queued orfaos (>6h) como ``failed`` e reembolsa o credito da geracao.

    Nao apaga o job (mantem para forense). Reutiliza ``_refund_job_credit`` para garantir a
    mesma logica de reembolso/integridade de creditos do resto do pipeline (job.credit_cost
    or 1). Idempotente: ``_refund_job_credit`` so reembolsa uma vez (status final guardado).
    """
    orphan_ids = asyncio.run(_find_orphan_queued_jobs_async())
    for job_id in orphan_ids:
        logger.warning(
            "Reaping orphan queued job %s (sem progresso ha >%dh) — marcando failed e reembolsando",
            job_id,
            ORPHAN_QUEUED_CUTOFF_HOURS,
        )
        _refund_job_credit(job_id, "failed", ORPHAN_QUEUED_ERROR)
    return len(orphan_ids)


# ── Watchdog de jobs travados em processamento ─────────────────────────────────
# Time limits do Celery NAO funcionam no pool solo do Windows (comprovado: task de
# compose com hard limit de 540s rodou 3h39). E uma task beat nao serve de vigia:
# ela entraria na MESMA fila solo que o job travado ocupa. Por isso o watchdog roda
# numa thread daemon do proprio processo do worker (o job ocupado esta em
# subprocess/IO, entao o GIL nao bloqueia a thread).

_WATCHDOG_INTERVAL_SECONDS = 300
_WATCHDOG_DEFAULT_LIMIT = 900
# Limiar de silencio (sem _update_job) por etapa, em segundos. Conservador de
# proposito: falso-positivo = job vivo morto + estorno indevido. As etapas longas
# (imagens IA, clipes IA) batem heartbeat por item, entao o silencio legitimo e curto.
_WATCHDOG_STEP_LIMITS = {
    "scripting": 300,
    "generating_images": 600,
    "generating_videos": 1500,
    "tts": 600,
    "transcribing": 300,
    "media": 900,
    "compositing": 1200,
    "finalizing": 300,
    # status "rendering" (re-render/export via Remotion)
    "preparing": 600,
    "encoding": 1800,
}
WATCHDOG_STUCK_ERROR = (
    "Geração interrompida por falta de progresso na etapa '{step}' (sem atualização há {minutes}min). "
    "O crédito foi devolvido."
)


def _watchdog_pass() -> int:
    """Varre os hashes ``job:*`` e mata jobs ativos com heartbeat estagnado.

    Acao dupla: seta a flag de cancelamento (a chain aborta no proximo checkpoint
    ``_check_cancelled``) e marca failed + estorna via ``_refund_job_credit``
    (idempotente — se a chain ainda estiver viva e cair no checkpoint, o cancel
    nao estorna de novo). Retorna quantos jobs foram ceifados.
    """
    reaped = 0
    now = datetime.now(timezone.utc)
    for raw_key in _redis.scan_iter(match="job:*", count=200):
        key = raw_key.decode() if isinstance(raw_key, bytes) else raw_key
        if key.count(":") != 1:
            continue  # flags auxiliares (job:{id}:cancelled etc.), nao o hash do job
        data = _redis.hgetall(key)
        status = data.get("status")
        if status not in ("processing", "rendering"):
            continue
        job_id = key.split(":", 1)[1]

        updated_raw = data.get("updated_at")
        if not updated_raw:
            # Job de antes do heartbeat existir: semeia a base agora e decide na
            # proxima passada (autocura, nunca mata sem referencia de tempo).
            _redis.hset(key, mapping={"updated_at": now.isoformat()})
            continue
        try:
            last_update = datetime.fromisoformat(updated_raw)
        except ValueError:
            _redis.hset(key, mapping={"updated_at": now.isoformat()})
            continue

        step = data.get("current_step") or ""
        limit = _WATCHDOG_STEP_LIMITS.get(step, _WATCHDOG_DEFAULT_LIMIT)
        elapsed = (now - last_update).total_seconds()
        if elapsed <= limit:
            continue

        # Re-checa na hora do abate: o finalize pode ter concluido entre o scan e ca.
        if _redis.hgetall(key).get("status") not in ("processing", "rendering"):
            continue

        message = WATCHDOG_STUCK_ERROR.format(step=step or "?", minutes=int(elapsed // 60))
        logger.error(
            "Watchdog: job %s travado (%s ha %.0fs > %ds) — cancelando e estornando", job_id, step, elapsed, limit
        )
        _redis_set(f"job:{job_id}:cancelled", "true")
        _refund_job_credit(job_id, "failed", message)
        _enqueue_dead_letter(job_id, message)
        reaped += 1
    return reaped


def _watchdog_loop() -> None:
    while True:
        try:
            reaped = _watchdog_pass()
            if reaped:
                logger.warning("Watchdog reaped %d stuck job(s)", reaped)
        except Exception:
            logger.exception("Watchdog pass falhou (segue tentando)")
        time.sleep(_WATCHDOG_INTERVAL_SECONDS)


try:  # pragma: no cover - wiring do worker real; testes chamam _watchdog_pass direto
    from celery.signals import worker_ready

    @worker_ready.connect
    def _start_watchdog_thread(**_kwargs):
        thread = threading.Thread(target=_watchdog_loop, daemon=True, name="stuck-job-watchdog")
        thread.start()
        logger.info("Watchdog de jobs travados ativo (passada a cada %ds)", _WATCHDOG_INTERVAL_SECONDS)
except ImportError:  # pragma: no cover
    pass


@celery_app.task(name="cleanup_old_jobs")
def cleanup_old_jobs() -> dict[str, int]:
    reaped = _reap_orphan_queued_jobs()
    result = asyncio.run(_cleanup_old_jobs_async())
    result["reaped_orphan_jobs"] = reaped
    return result


@celery_app.task(name="cleanup_orphan_files")
def cleanup_orphan_files() -> dict[str, int]:
    return asyncio.run(_cleanup_orphan_files_async())


@celery_app.task(name="generate_script", bind=True, soft_time_limit=120, time_limit=150)
def task_generate_script(
    self,
    job_id: str,
    topic: str,
    style: str,
    duration_target: int,
    template_id: str = "stock_narration",
    trend_context: str | None = None,
) -> dict:
    try:
        if _check_cancelled(job_id):
            return {"cancelled": True}
        _update_job(job_id, "processing", "scripting", 0.1, detail="Gerando roteiro com IA...")
        script = generate_script(topic, style, duration_target, template_id=template_id, trend_context=trend_context)
        job_dir = get_job_dir(job_id)
        (job_dir / "script.json").write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")

        # Validate script
        scenes = script.get("scenes", [])
        if not scenes:
            raise ValueError("Script has no scenes")
        total_dur = sum(s.get("duration_hint", 7) for s in scenes)
        logger.info(
            f"Script: {len(scenes)} scenes, {total_dur}s total, {len(script.get('narration', '').split())} words"
        )

        # Q7: cascata caiu no provedor free = roteiro de qualidade reduzida. Flag no hash
        # (grid le em tempo real) + o llm_provider dentro do script persiste no Postgres.
        from app.services.llm import DEGRADED_PROVIDER_LABEL

        if script.get("llm_provider") == DEGRADED_PROVIDER_LABEL:
            # mapping= (nao posicional): assinatura unica que o FakeRedis dos testes suporta.
            _redis.hset(f"job:{job_id}", mapping={"degraded": "1"})
            logger.warning(f"Job {job_id}: roteiro atendido pelo provedor FREE (qualidade reduzida).")

        _update_job(job_id, "processing", "scripting", 0.16, detail="Roteiro gerado com sucesso.")
        script["_duration_target"] = duration_target
        return script
    except SoftTimeLimitExceeded as e:
        _retry_or_fail(self, job_id, e, "Script generation timed out (LLM demorou demais).", [10, 30])
    except Exception as e:
        _retry_or_fail(self, job_id, e, f"Script generation failed: {e}", [10, 30])


@celery_app.task(name="synthesize_audio", bind=True, soft_time_limit=120, time_limit=150)
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
        template = get_template(template_id)

        if template.script.is_dialogue:
            from app.services.dialogue import synthesize_dialogue

            synthesize_dialogue(script["scenes"], output_path, duration_target=duration_target)
        elif voice_provider_name == "custom":
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
            if not voice_id and template.voice.provider == "elevenlabs":
                voice_id = template.voice.voice_id
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
            voice_id = (voice_config or {}).get(
                "voice_id",
                template.voice.voice_id if template.voice.provider == "edge" else "pt-BR-AntonioNeural",
            )
            rate = (voice_config or {}).get("rate", template.voice.rate if template.voice.provider == "edge" else -10)
            pitch = (voice_config or {}).get("pitch", template.voice.pitch if template.voice.provider == "edge" else 5)
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
    except SoftTimeLimitExceeded as e:
        _retry_or_fail(self, job_id, e, "TTS timed out (sintetizacao demorou demais).", [5, 15])
    except Exception as e:
        _retry_or_fail(self, job_id, e, f"TTS failed: {e}", [5, 15])


@celery_app.task(name="transcribe_audio", bind=True, soft_time_limit=120, time_limit=150)
def task_transcribe_audio(self, audio_path: str, job_id: str) -> dict:
    try:
        if not audio_path or _check_cancelled(job_id):
            return {"cancelled": True}
        _update_job(job_id, "processing", "transcribing", 0.45, detail="Transcrevendo com Whisper...")
        words = transcribe_with_timestamps(audio_path)
        job_dir = get_job_dir(job_id)
        (job_dir / "words.json").write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
        script = _read_json_file(job_dir / "script.json")

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


@celery_app.task(name="fetch_media", bind=True, soft_time_limit=300, time_limit=360)
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
        if template.media.source == "ai_video":
            video_paths = data.get("video_paths")
            if not video_paths:
                vid_dir = get_job_dir(job_id) / "videos"
                video_paths = sorted(str(p) for p in vid_dir.glob("scene_*.mp4"))
            data["media_paths"] = video_paths
            _update_job(job_id, "processing", "media", 0.65, detail="Clipes IA ja gerados, skip Pexels.")
            return data
        _update_job(job_id, "processing", "media", 0.55, detail="Buscando videos...")
        script = data["script"]
        job_dir = get_job_dir(job_id)
        media_dir = job_dir / "media"
        media_dir.mkdir(exist_ok=True)

        media_paths = []

        if template.media.source == "local":
            # Biblioteca local (Drive): 1 clip/cena por busca semantica (CLIP) + pool
            # anti-repeticao. Fallback aleatorio se nao houver embeddings/dep. loop_single
            # => 1 clip (busca pelo tema) pro video todo.
            from app.services.drive_library import search_clips

            tag = template.media.library_tag or "satisfying"
            topic = data.get("topic", "")
            if template.media.loop_single:
                clips = search_clips(topic, tag, k=1)
                clip = clips[0] if clips else pick_clip(tag)
                if clip is None:
                    raise RuntimeError(f"No clips in library '{tag}'")
                dest = str(media_dir / "background.mp4")
                shutil.copy2(str(clip), dest)
                media_paths = [dest]
                logger.info(f"Local clip (semantic): {clip.name} (will loop)")
            else:
                used_names: set[str] = set()
                for i, scene in enumerate(script["scenes"]):
                    if _check_cancelled(job_id):
                        return {"cancelled": True}
                    kw = scene.get("keywords_en") or []
                    query = scene.get("visual_hint") or (kw[0] if kw else None) or scene.get("text") or topic
                    _update_job(
                        job_id,
                        "processing",
                        "media",
                        0.55,
                        detail=f"Buscando fundo (cena {i + 1}/{len(script['scenes'])})...",
                    )
                    clips = search_clips(query, tag, k=1, exclude=used_names)
                    clip = clips[0] if clips else pick_clip(tag)
                    if clip is None:
                        logger.warning(f"Cena {i}: sem clip para tag '{tag}'")
                        continue
                    used_names.add(clip.name)
                    dest = str(media_dir / f"scene_{i}.mp4")
                    shutil.copy2(str(clip), dest)
                    media_paths.append(dest)
                    logger.info(f"Cena {i}: fundo '{clip.name}' (query='{str(query)[:40]}')")
        else:
            # Pexels per-scene: ranqueia candidatos e baixa o melhor ainda nao usado
            used_clips: set[str] = set()
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
                ordered = order_candidates(results, scene, used_clips)
                if not ordered:
                    logger.warning(f"Scene {i}: no media found for {keywords}")
                    continue
                dest = str(media_dir / f"scene_{i}.mp4")
                for cand in ordered:
                    try:
                        asyncio.run(download_media(cand["url"], dest))
                        media_paths.append(dest)
                        used_clips.add(cand["url"])
                        logger.info(f"Scene {i}: downloaded '{keywords[0]}' (dur={cand.get('duration')}s)")
                        break
                    except Exception as e:
                        logger.warning(f"Scene {i}: download failed, trying next candidate: {e}")
                else:
                    logger.error(f"Scene {i}: all downloads failed")

        if not media_paths:
            raise RuntimeError("No media available")

        logger.info(f"Media: {len(media_paths)} file(s) ready")
        _update_job(job_id, "processing", "media", 0.65, detail="Midias prontas.")
        data["media_paths"] = media_paths
        return data
    except SoftTimeLimitExceeded as e:
        _retry_or_fail(self, job_id, e, "Media fetch timed out (downloads demoraram demais).", [10, 30, 60])
    except Exception as e:
        _retry_or_fail(self, job_id, e, f"Media fetch failed: {e}", [10, 30, 60])


@celery_app.task(name="compose_video", bind=True, soft_time_limit=480, time_limit=540)
def task_compose_video(self, data: dict, job_id: str, template_id: str = "stock_narration") -> str:
    try:
        if data.get("cancelled") or _check_cancelled(job_id):
            return ""
        from app.templates import get_template

        template = get_template(template_id)

        _update_job(job_id, "processing", "compositing", 0.7, detail="Montando video com FFmpeg...")
        job_dir = get_job_dir(job_id)
        output_path = str(job_dir / "final.mp4")

        from app.job_config import resolve_job_flag

        audio_path = data["audio_path"]
        if resolve_job_flag(_redis, job_id, "sfx_enabled", settings.SFX_ENABLED):
            from app.services.sfx import mix_transitions

            scene_durs = [s.get("duration_hint", 0) for s in data["script"]["scenes"]]
            audio_path = mix_transitions(audio_path, scene_durs, str(job_dir / "narration_sfx.wav"))

        from app.services.music import resolve_music_path

        music_enabled = resolve_job_flag(_redis, job_id, "music_enabled", settings.AUTO_MUSIC_ENABLED)
        music_path = resolve_music_path(template_id) if music_enabled else None
        compose_short(
            scenes=data["script"]["scenes"],
            media_paths=data["media_paths"],
            audio_path=audio_path,
            words=data["words"],
            output_path=output_path,
            layout=template.layout,
            music_path=music_path,
            music_volume=settings.AUTO_MUSIC_VOLUME,
            overlays=data["script"].get("overlays"),
        )
        _update_job(job_id, "processing", "compositing", 0.9, detail="Video montado.")
        if settings.QUALITY_GATE_ENABLED:
            from app.services.quality import inspect_render

            target = data.get("script", {}).get("_duration_target", 0)
            report = inspect_render(output_path, target)
            if not report.ok:
                warning = "; ".join(report.warnings)
                _redis.hset(f"job:{job_id}", "quality_warning", warning)
                logger.warning("Job %s quality gate: %s", job_id, warning)
        return output_path
    except SoftTimeLimitExceeded:
        _handle_soft_timeout(job_id, "compose_video")
        raise
    except Exception as e:
        _fail_job(job_id, f"Compositing failed: {e}")
        raise


@celery_app.task(name="finalize", bind=True, soft_time_limit=120, time_limit=150)
def task_finalize(self, video_path: str, job_id: str) -> str:
    try:
        if not video_path or _check_cancelled(job_id):
            return ""
        _update_job(job_id, "processing", "finalizing", 0.95, detail="Salvando video final...")
        output_dir = get_output_dir()
        final_path = str(output_dir / f"{job_id}.mp4")
        final_src = append_outro(video_path)  # selo de marca (~1.5s); no-op-safe se off/asset ausente/erro
        shutil.copy2(final_src, final_path)
        if final_src != video_path:
            Path(final_src).unlink(missing_ok=True)
        _write_thumbnail(final_path, str(output_dir / f"{job_id}.jpg"))

        # Save script to PostgreSQL for the editor (keep job dir for editing)
        try:
            from sqlalchemy import update

            from app.db.engine import worker_session as async_session  # NullPool: seguro com asyncio.run() por task
            from app.db.models import Job

            job_dir = get_job_dir(job_id)
            script_path = job_dir / "script.json"
            script_data = _read_json_file(script_path) if script_path.exists() else None

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


@celery_app.task(name="rerender_video", bind=True, soft_time_limit=300, time_limit=360)
def task_rerender_video(self, job_id: str) -> str:
    """Re-render the edited video for export.

    Hybrid engine: Remotion (fiel ao preview) by default, FFmpeg+NVENC as fallback
    via settings.RENDER_ENGINE. Runs in background — user never waits.
    """
    try:
        if _check_cancelled(job_id):
            return ""
        _update_job(job_id, "rendering", "preparing", 0.05, detail="Preparando arquivos para re-render...")
        job_dir = get_job_dir(job_id)
        from app.config import BASE_DIR, settings
        from app.services.compositor import compose_short

        script_path = job_dir / "script.json"
        if not script_path.exists():
            raise RuntimeError("script.json not found")
        script = _read_json_file(script_path)

        words_path = job_dir / "words.json"
        words = _read_json_file(words_path) if words_path.exists() else []

        audio_path = str(job_dir / "narration.wav")
        if not Path(audio_path).exists():
            raise RuntimeError("narration.wav not found")

        from app.job_config import resolve_job_flag
        from app.services.music import auto_music_url

        template_id = _redis_hget(f"job:{job_id}", "template_id") or "stock_narration"

        audio_basename = "narration.wav"
        if resolve_job_flag(_redis, job_id, "sfx_enabled", settings.SFX_ENABLED):
            from app.services.sfx import mix_transitions

            scene_durs = [s.get("duration_hint", 0) for s in script.get("scenes", [])]
            audio_path = mix_transitions(audio_path, scene_durs, str(job_dir / "narration_sfx.wav"))
            audio_basename = Path(audio_path).name  # narration_sfx.wav se mixou; senao narration.wav

        music_enabled = resolve_job_flag(_redis, job_id, "music_enabled", settings.AUTO_MUSIC_ENABLED)
        default_music_url = auto_music_url(template_id) if music_enabled else None

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
            editor_state = json.loads(editor_state_path.read_text(encoding="utf-8"))
            comp_data = editor_state.get("composition", {})

        if settings.RENDER_ENGINE == "remotion":
            from app.services.remotion import invoke_remotion_render

            output_path = str(job_dir / "final_remotion.mp4")
            _update_job(job_id, "rendering", "encoding", 0.2, detail="Renderizando com Remotion...")
            logger.info(f"Starting Remotion re-render for job {job_id}")
            invoke_remotion_render(
                job_id,
                output_path,
                audio_filename=audio_basename,
                default_music_url=default_music_url,
                on_progress=lambda p: _update_job(
                    job_id,
                    "rendering",
                    "encoding",
                    0.2 + (p / 100) * 0.7,
                    detail=f"Renderizando com Remotion... {p}%",
                ),
            )
        else:
            # FFmpeg+NVENC fallback path
            music_path = None
            music_url = comp_data.get("musicUrl", default_music_url)
            if music_url:
                music_file = BASE_DIR / "frontend" / "public" / music_url.lstrip("/")
                if music_file.exists():
                    music_path = str(music_file)

            output_path = str(job_dir / "final_edited.mp4")
            _update_job(job_id, "rendering", "encoding", 0.2, detail="Re-renderizando video...")
            logger.info(f"Starting FFmpeg+NVENC re-render for job {job_id}")

            from app.templates import get_template

            re_template = get_template(template_id)

            compose_short(
                scenes=script.get("scenes", []),
                media_paths=media_paths,
                audio_path=audio_path,
                words=words,
                output_path=output_path,
                music_path=music_path,
                music_volume=comp_data.get("musicVolume", settings.AUTO_MUSIC_VOLUME),
                subtitle_style=comp_data.get("subtitleStyle"),
                layout=re_template.layout,
                overlays=comp_data.get("overlays"),
            )

        _update_job(job_id, "rendering", "finalizing", 0.9, detail="Finalizando re-render...")

        # Copy to output dir (becomes downloadable version)
        output_dir = get_output_dir()
        final_path = str(output_dir / f"{job_id}.mp4")
        final_src = append_outro(output_path)  # selo de marca tambem no export editado (no-op-safe)
        shutil.copy2(final_src, final_path)
        if final_src != output_path:
            Path(final_src).unlink(missing_ok=True)
        _write_thumbnail(final_path, str(output_dir / f"{job_id}.jpg"))

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
