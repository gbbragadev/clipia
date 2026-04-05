from contextlib import asynccontextmanager

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.routes import router
from app.auth.routes import router as auth_router
from app.payments.routes import router as payments_router
from app.config import settings
from app.db.engine import engine
from app.errors import (
    ErrorMessages,
    pydantic_validation_exception_handler,
    request_validation_exception_handler,
    unhandled_exception_handler,
)
from app.observability import access_log_middleware, get_deep_health, render_metrics

logger = logging.getLogger(__name__)


def _get_cors_origins() -> list[str]:
    raw = settings.CORS_ORIGINS
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


limiter = Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT_DEFAULT])


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="ClipIA API", version="0.1.0", lifespan=lifespan)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.add_exception_handler(ValidationError, pydantic_validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.middleware("http")(access_log_middleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_get_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"],
    )

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(router, prefix="/api/v1")
    app.include_router(payments_router, prefix="/api/v1")

    jobs_dir = settings.STORAGE_DIR / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/storage/jobs", StaticFiles(directory=str(jobs_dir)), name="job_files")

    @app.get(
        "/health",
        tags=["system"],
        summary="Check system health",
        description="Returns a simple OK status to indicate the API is running.",
        responses={200: {"description": "System is healthy", "content": {"application/json": {"example": {"status": "ok"}}}}},
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
        responses={200: {"description": "All systems operational"}, 503: {"description": "One or more subsystems failing"}},
    )
    async def health_deep():
        """
        Deep system health check.

        Performs connection tests to the database, caching layers, and any external
        services required for full functionality. Returns a detailed status report.
        """
        return await get_deep_health(app.version)

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
