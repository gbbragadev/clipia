from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.routes import router
from app.auth.routes import router as auth_router
from app.payments.routes import router as payments_router
from app.config import settings
from app.db.engine import engine


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
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
