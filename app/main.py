from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.auth.routes import router as auth_router
from app.payments.routes import router as payments_router
from app.config import settings
from app.db.engine import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title="ClipIA API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(router, prefix="/api/v1")
app.include_router(payments_router, prefix="/api/v1")

# Serve job assets (media, audio, subtitles) for the Remotion editor
jobs_dir = settings.STORAGE_DIR / "jobs"
jobs_dir.mkdir(parents=True, exist_ok=True)
app.mount("/storage/jobs", StaticFiles(directory=str(jobs_dir)), name="job_files")


@app.get("/health")
def health():
    return {"status": "ok"}
