from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api import routes as api_routes
from app.auth.service import hash_password
from app.config import settings
from app.db.base import Base
from app.db.models import Job, User, VoiceClone
from app.worker import tasks as worker_tasks

VALID_WAV = b"RIFF\x10\x00\x00\x00WAVEfmt "


def run(coro):
    return asyncio.run(coro)


class FakeRedis:
    def __init__(self):
        self.data: dict[str, dict[str, str]] = {}
        self.values: dict[str, str] = {}

    def hset(self, key: str, mapping: dict[str, str]):
        self.data.setdefault(key, {}).update({k: str(v) for k, v in mapping.items()})

    def hgetall(self, key: str) -> dict[str, str]:
        return dict(self.data.get(key, {}))

    def hget(self, key: str, field: str) -> str | None:
        return self.data.get(key, {}).get(field)

    def set(self, key: str, value: str, ex: int | None = None, nx: bool = False):
        if nx and key in self.values:
            return None
        self.values[key] = str(value)
        return True

    def get(self, key: str) -> str | None:
        return self.values.get(key)

    def delete(self, key: str):
        self.data.pop(key, None)
        self.values.pop(key, None)


@dataclass
class DummyUpload:
    filename: str
    content: bytes
    content_type: str = "audio/wav"
    offset: int = 0

    async def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self.content) - self.offset
        chunk = self.content[self.offset : self.offset + size]
        self.offset += len(chunk)
        return chunk


class DummyForm:
    def __init__(
        self,
        *,
        file: DummyUpload | None = None,
        files: list[DummyUpload] | None = None,
        fields: dict[str, str] | None = None,
    ):
        self.file = file
        self.files = files or []
        self.fields = fields or {}

    def get(self, key: str):
        if key == "file":
            return self.file
        return self.fields.get(key)

    def getlist(self, key: str):
        return self.files if key == "files" else []


class DummyRequest:
    def __init__(self, form: DummyForm | None = None, raw_body: bytes | None = None):
        self._form = form or DummyForm()
        self._raw_body = raw_body or b""

    async def form(self):
        return self._form

    async def body(self):
        return self._raw_body


@dataclass
class TestEnv:
    session_factory: async_sessionmaker[AsyncSession]
    storage_dir: Path
    fake_redis: FakeRedis
    verified_user: User
    other_verified_user: User


def create_test_env(tmp_path: Path, monkeypatch) -> TestEnv:
    db_path = tmp_path / "test.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with session_factory() as session:
            verified_user = User(
                email="verified@example.com",
                name="Verified User",
                password_hash=hash_password("supersecret"),
                credits=10,
                email_verified=True,
                verification_code=None,
                verification_expires=None,
            )
            other_verified_user = User(
                email="other@example.com",
                name="Other User",
                password_hash=hash_password("supersecret"),
                credits=10,
                email_verified=True,
                verification_code=None,
                verification_expires=None,
            )
            session.add_all([verified_user, other_verified_user])
            await session.commit()
            await session.refresh(verified_user)
            await session.refresh(other_verified_user)
            return verified_user, other_verified_user

    storage_dir = tmp_path / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "STORAGE_DIR", storage_dir)
    fake_redis = FakeRedis()
    monkeypatch.setattr(api_routes, "_redis", fake_redis)
    monkeypatch.setattr(worker_tasks, "_redis", fake_redis)

    verified_user, other_verified_user = run(_setup())
    return TestEnv(
        session_factory=session_factory,
        storage_dir=storage_dir,
        fake_redis=fake_redis,
        verified_user=verified_user,
        other_verified_user=other_verified_user,
    )


def create_job(env: TestEnv, **kwargs) -> Job:
    async def _create():
        async with env.session_factory() as session:
            job = Job(
                user_id=kwargs.get("user_id", env.verified_user.id),
                topic=kwargs.get("topic", "Topic"),
                style=kwargs.get("style", "educational"),
                duration_target=kwargs.get("duration_target", 45),
                status=kwargs.get("status", "queued"),
                pending_credits=kwargs.get("pending_credits", 0.0),
                editor_state=kwargs.get("editor_state"),
                script=kwargs.get("script"),
                template_id=kwargs.get("template_id", "stock_narration"),
                credit_cost=kwargs.get("credit_cost", 1),
                voice_provider=kwargs.get("voice_provider", "edge"),
                voice_config=kwargs.get("voice_config"),
            )
            session.add(job)
            await session.commit()
            await session.refresh(job)
            return job

    return run(_create())


def create_clone(env: TestEnv, *, user_id=None, name="Minha voz", external_voice_id="el_clone_123") -> VoiceClone:
    async def _create():
        async with env.session_factory() as session:
            clone = VoiceClone(
                user_id=user_id or env.verified_user.id,
                name=name,
                provider="elevenlabs",
                external_voice_id=external_voice_id,
                samples_count=1,
            )
            session.add(clone)
            await session.commit()
            await session.refresh(clone)
            return clone

    return run(_create())
