import asyncio
import json
import logging
import os
import re
import shutil
import time
import uuid
from collections import Counter
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from fastapi import Request
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.service import decode_access_token
from app.config import settings
from app.db.engine import build_engine
from app.db.models import CreditPurchase, Job, JobDispatch
from app.payments.states import canonical_payment_state_expression
from app.redis_pool import get_redis
from app.worker.celery_app import celery_app

logger = logging.getLogger("clipia.access")

_START_TIME = time.monotonic()
_REQUEST_COUNTS: Counter[tuple[str, str, str]] = Counter()
_CREDIT_TOTALS: Counter[str] = Counter()
_AUTH_TRANSPORT_COUNTS: Counter[str] = Counter()
_METRIC_LOCK = Lock()
_HEALTH_CACHE: dict[str, Any] = {"expires_at": 0.0, "payload": None}
_PUBLIC_SHARE_LOG_PATH = re.compile(r"^/api/v1/public-shares/[^/]+(?P<suffix>/.*)?$")


def record_request_metric(method: str, path: str, status_code: int) -> None:
    with _METRIC_LOCK:
        _REQUEST_COUNTS[(method, path, str(status_code))] += 1


def record_credit_metric(kind: str, amount: float) -> None:
    if amount <= 0:
        return
    with _METRIC_LOCK:
        _CREDIT_TOTALS[kind] += amount


def record_auth_transport(transport: str) -> None:
    if transport not in {"bearer", "cookie"}:
        return
    with _METRIC_LOCK:
        _AUTH_TRANSPORT_COUNTS[transport] += 1


def _metric_path(request: Request) -> str:
    fastapi_scope = request.scope.get("fastapi")
    if isinstance(fastapi_scope, dict):
        effective_context = fastapi_scope.get("effective_route_context")
        effective_path = getattr(effective_context, "path", None)
        if isinstance(effective_path, str) and effective_path:
            return effective_path

    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    if isinstance(route_path, str) and route_path:
        return route_path
    return "__unmatched__"


def _access_log_path(path: str) -> tuple[str, bool]:
    match = _PUBLIC_SHARE_LOG_PATH.fullmatch(path)
    if match is None:
        return path, False
    return f"/api/v1/public-shares/[redacted]{match.group('suffix') or ''}", True


async def access_log_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]
    start = time.perf_counter()
    response = await call_next(request)

    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    path = request.url.path
    logged_path, is_public_share = _access_log_path(path)
    record_request_metric(request.method, _metric_path(request), response.status_code)

    if path not in {"/health", "/health/deep"}:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "method": request.method,
            "path": logged_path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "request_id": request_id,
        }
        if path != "/api/v1/analytics/events":
            user_id = None
            auth_header = request.headers.get("authorization", "")
            if auth_header.lower().startswith("bearer "):
                user_id = decode_access_token(auth_header.split(" ", 1)[1])
            if not is_public_share:
                payload["client_ip"] = request.client.host if request.client else None
            payload["user_id"] = user_id
        logger.info(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))

    response.headers["X-Request-ID"] = request_id
    return response


async def get_deep_health(version: str) -> dict[str, Any]:
    now = time.monotonic()
    cached = _HEALTH_CACHE.get("payload")
    if cached is not None and now < _HEALTH_CACHE["expires_at"]:
        return cached

    payload = await _compute_deep_health(version)
    _HEALTH_CACHE["payload"] = payload
    _HEALTH_CACHE["expires_at"] = now + 10
    return payload


async def _compute_deep_health(version: str) -> dict[str, Any]:
    database = await _check_database()
    redis_check = await _check_redis()
    storage = await _check_storage()
    celery = await _check_celery()

    statuses = {
        "database": database["status"],
        "redis": redis_check["status"],
        "storage": storage["status"],
        "celery": celery["status"],
    }
    if statuses["database"] == "down" or statuses["redis"] == "down":
        overall = "unhealthy"
    elif statuses["celery"] == "down":
        overall = "degraded"
    else:
        overall = "healthy"

    return {
        "status": overall,
        "checks": {
            "database": database,
            "redis": redis_check,
            "storage": storage,
            "celery": celery,
        },
        "version": version,
        "git_sha": settings.GIT_SHA,
        "app_version": version,
        "deployed_at": settings.DEPLOYED_AT,
        "uptime_seconds": int(time.monotonic() - _START_TIME),
    }


@asynccontextmanager
async def _runtime_session() -> AsyncSession:
    engine = build_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def _check_database() -> dict[str, Any]:
    start = time.perf_counter()
    try:
        async with asyncio.timeout(3):
            async with _runtime_session() as session:
                await session.execute(text("SELECT 1"))
        return {"status": "up", "latency_ms": round((time.perf_counter() - start) * 1000, 2)}
    except Exception:
        return {"status": "down", "latency_ms": round((time.perf_counter() - start) * 1000, 2)}


def _redis_ping() -> bool:
    client = get_redis()
    return bool(client.ping())


async def _check_redis() -> dict[str, Any]:
    start = time.perf_counter()
    try:
        async with asyncio.timeout(2):
            await asyncio.to_thread(_redis_ping)
        return {"status": "up", "latency_ms": round((time.perf_counter() - start) * 1000, 2)}
    except Exception:
        return {"status": "down", "latency_ms": round((time.perf_counter() - start) * 1000, 2)}


def _storage_check() -> dict[str, Any]:
    settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    writable = os.access(settings.STORAGE_DIR, os.W_OK)
    usage = shutil.disk_usage(settings.STORAGE_DIR)
    status = "up" if writable else "down"
    return {
        "status": status,
        "writable": writable,
        "free_gb": round(usage.free / (1024**3), 2),
    }


async def _check_storage() -> dict[str, Any]:
    return await asyncio.to_thread(_storage_check)


def _celery_ping() -> list[dict[str, str]] | None:
    return celery_app.control.ping(timeout=2)


async def _check_celery() -> dict[str, Any]:
    try:
        async with asyncio.timeout(3):
            replies = await asyncio.to_thread(_celery_ping)
        workers = len(replies or [])
        status = "up" if workers > 0 else "down"
        return {"status": status, "workers": workers}
    except Exception:
        return {"status": "down", "workers": 0}


async def render_metrics() -> str:
    active_jobs = await _get_active_job_counts()
    credit_totals = await _get_credit_totals()
    process_credit_totals = _snapshot_credit_totals()
    request_counts = _snapshot_request_counts()
    auth_transport_counts = _snapshot_auth_transport_counts()

    lines = [
        "# HELP clipia_requests_total Total requests",
        "# TYPE clipia_requests_total counter",
    ]
    for (method, path, status_code), count in sorted(request_counts.items()):
        lines.append(f'clipia_requests_total{{method="{method}",path="{path}",status="{status_code}"}} {count}')

    lines.extend(
        [
            "",
            "# HELP clipia_active_jobs Active jobs by status",
            "# TYPE clipia_active_jobs gauge",
        ]
    )
    for status, count in sorted(active_jobs.items()):
        lines.append(f'clipia_active_jobs{{status="{status}"}} {count}')

    lines.extend(
        [
            "",
            "# HELP clipia_credits_total Authoritative credits from durable database state",
            "# TYPE clipia_credits_total counter",
        ]
    )
    for kind, amount in (("credit", credit_totals["purchased"]), ("debit", credit_totals["consumed"])):
        lines.append(f'clipia_credits_total{{type="{kind}"}} {amount}')

    lines.extend(
        [
            "",
            "# HELP clipia_credit_mutations_process_total Process-local mutation observations; resets on restart",
            "# TYPE clipia_credit_mutations_process_total counter",
        ]
    )
    for kind, amount in sorted(process_credit_totals.items()):
        lines.append(f'clipia_credit_mutations_process_total{{type="{kind}"}} {amount}')

    lines.extend(
        [
            "",
            "# HELP clipia_auth_transport_total Authenticated requests by phase-one transport",
            "# TYPE clipia_auth_transport_total counter",
        ]
    )
    for transport, count in sorted(auth_transport_counts.items()):
        lines.append(f'clipia_auth_transport_total{{transport="{transport}"}} {count}')

    return "\n".join(lines) + "\n"


def _snapshot_request_counts() -> Counter[tuple[str, str, str]]:
    with _METRIC_LOCK:
        return Counter(_REQUEST_COUNTS)


def _snapshot_credit_totals() -> Counter[str]:
    with _METRIC_LOCK:
        return Counter(_CREDIT_TOTALS)


def _snapshot_auth_transport_counts() -> Counter[str]:
    with _METRIC_LOCK:
        return Counter(_AUTH_TRANSPORT_COUNTS)


async def _get_active_job_counts() -> dict[str, int]:
    # Inclui 'failed' e 'completed' (nao so os ativos): sem isso, um pico de jobs falhados nao
    # dispara alerta via /metrics — o dono lancaria cego pra taxa de erro (objetivo: acompanhar uso).
    _JOB_STATUSES = ("queued", "processing", "failed", "completed")
    async with _runtime_session() as session:
        result = await session.execute(
            select(Job.status, func.count()).where(Job.status.in_(_JOB_STATUSES)).group_by(Job.status)
        )
    counts = {status: count for status, count in result.all()}
    for status in _JOB_STATUSES:
        counts.setdefault(status, 0)
    return counts


async def _get_credit_totals() -> dict[str, float]:
    async with _runtime_session() as session:
        canonical_state = canonical_payment_state_expression(
            CreditPurchase.status,
            CreditPurchase.payment_state,
        )
        purchased = await session.scalar(
            select(
                func.coalesce(
                    func.sum(CreditPurchase.credits_amount + CreditPurchase.bonus_credits),
                    0,
                )
            ).where(canonical_state == "paid")
        )
        consumed = await session.scalar(
            select(func.coalesce(func.sum(JobDispatch.debited_credits), 0)).where(JobDispatch.state == "completed")
        )
    return {
        "purchased": float(purchased or 0),
        "consumed": float(consumed or 0),
    }
