import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes import router
from app.auth.routes import router as auth_router
from app.config import BASE_DIR, settings
from app.db.engine import engine
from app.errors import (
    ErrorMessages,
    pydantic_validation_exception_handler,
    request_validation_exception_handler,
    unhandled_exception_handler,
)
from app.observability import access_log_middleware, get_deep_health, render_metrics
from app.payments.routes import router as payments_router
from app.utils.media_url import PRIVATE_PREFIX, verify_media_sig
from app.utils.ratelimit import client_ip

logger = logging.getLogger(__name__)


def _get_cors_origins() -> list[str]:
    raw = settings.CORS_ORIGINS
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


limiter = Limiter(key_func=client_ip, default_limits=[settings.RATE_LIMIT_DEFAULT])


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.config import validate_production_settings

    validate_production_settings(settings)
    yield
    await engine.dispose()


async def media_guard_middleware(request: Request, call_next):
    """Protege a midia privada (/storage/jobs/*): exige assinatura ?exp&sig valida.

    A galeria publica (/storage/showcase) e qualquer outra rota passam direto.
    """
    if request.method in ("GET", "HEAD") and request.url.path.startswith(PRIVATE_PREFIX):
        if not verify_media_sig(
            request.url.path,
            request.query_params.get("exp"),
            request.query_params.get("sig"),
        ):
            return JSONResponse(
                status_code=403, content={"detail": "Midia protegida: assinatura invalida ou expirada."}
            )
    return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


def create_app() -> FastAPI:
    app = FastAPI(title="ClipIA API", version=settings.APP_VERSION, lifespan=lifespan)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.add_exception_handler(ValidationError, pydantic_validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.middleware("http")(access_log_middleware)
    app.middleware("http")(media_guard_middleware)

    app.add_middleware(SecurityHeadersMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_get_cors_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
        expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"],
    )

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(router, prefix="/api/v1")
    app.include_router(payments_router, prefix="/api/v1")

    jobs_dir = settings.STORAGE_DIR / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/storage/jobs", StaticFiles(directory=str(jobs_dir)), name="job_files")

    # Videos da galeria/showcase servidos via /storage/showcase (rewrite /storage/* do
    # next.config proxia pro backend). Mantem os mp4 fora do git do frontend; o manifesto
    # (showcase.json) aponta /storage/showcase/<slug>.mp4 para esses, ou /showcase/<slug>.mp4
    # para os poucos "hero" commitados em frontend/public/showcase.
    showcase_dir = settings.STORAGE_DIR / "showcase"
    showcase_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/storage/showcase", StaticFiles(directory=str(showcase_dir)), name="showcase_files")

    # Trilhas de musica (frontend/public/music) servidas tambem pelo backend, para que o
    # render server-side do Remotion baixe a musica via URL absoluta (igual audio/midia). O
    # preview no editor continua usando o /music/*.mp3 servido pelo Next em frontend/public.
    music_dir = BASE_DIR / "frontend" / "public" / "music"
    if music_dir.exists():
        app.mount("/music", StaticFiles(directory=str(music_dir)), name="music_files")

    @app.get(
        "/health",
        tags=["system"],
        summary="Check system health",
        description="Returns a simple OK status to indicate the API is running.",
        responses={
            200: {"description": "System is healthy", "content": {"application/json": {"example": {"status": "ok"}}}}
        },
    )
    def health():
        """
        Check system health.

        Returns a simple JSON payload to indicate that the API is up and running.
        Useful for load balancers and simple health checks.
        """
        return {"status": "ok"}

    @app.get(
        "/health/deep",
        tags=["system"],
        summary="Deep system health check",
        description="Checks all internal dependencies and backing services (DB, Redis, etc.).",
        responses={
            200: {"description": "All systems operational"},
            503: {"description": "One or more subsystems failing"},
        },
    )
    async def health_deep():
        """
        Deep system health check.

        Performs connection tests to the database, caching layers, and any external
        services required for full functionality. Returns a detailed status report.
        """
        return await get_deep_health(settings.APP_VERSION)

    @app.get(
        "/metrics",
        response_class=PlainTextResponse,
        tags=["system"],
        summary="Prometheus metrics",
        description="Exposes application metrics for Prometheus scraping.",
        responses={200: {"description": "Metrics data in Prometheus format"}},
    )
    async def metrics():
        """
        Prometheus metrics.

        Returns application metrics including request rates, latency, and resource usage
        in the standard Prometheus plain-text format.
        """
        return PlainTextResponse(await render_metrics(), media_type="text/plain; version=0.0.4")

    return app


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    logger.info("Rate limit exceeded on %s %s: %s", request.method, request.url.path, exc.detail)
    return JSONResponse(status_code=429, content={"detail": ErrorMessages.RATE_LIMITED})


app = create_app()
