import os
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("OPEN_ROUTER_API_KEY", "test-key")
os.environ.setdefault("PEXELS_API_KEY", "test-key")

from app.api import routes as api_routes
from app.auth import routes as auth_routes
from app.auth.service import create_access_token
from app.config import settings
from app.db.base import Base
from app.db.engine import get_db
from app.db.models import CreditPurchase, Job, User
from app.main import create_app
from app.payments.schemas import CREDIT_PACKAGES
from app.worker import tasks as worker_tasks


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

    def set(self, key: str, value: str):
        self.values[key] = str(value)

    def get(self, key: str) -> str | None:
        return self.values.get(key)

    def delete(self, key: str):
        self.data.pop(key, None)
        self.values.pop(key, None)

    def clear(self):
        self.data.clear()
        self.values.clear()


@pytest.fixture(autouse=True)
def reset_rate_limiters():
    for limiter in (auth_routes.limiter, api_routes.limiter):
        storage = getattr(limiter, "_storage", None)
        if storage is not None and hasattr(storage, "reset"):
            storage.reset()


@pytest_asyncio.fixture
async def test_db(tmp_path, monkeypatch):
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir()

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

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setattr(settings, "STORAGE_DIR", storage_dir)
    monkeypatch.setattr(settings, "CORS_ORIGINS", "http://localhost:3003")
    monkeypatch.setattr(settings, "MP_WEBHOOK_SECRET", "")

    async def override_get_db():
        async with session_factory() as session:
            yield session

    yield {
        "engine": engine,
        "session_factory": session_factory,
        "override_get_db": override_get_db,
        "storage_dir": storage_dir,
    }

    await engine.dispose()


@pytest_asyncio.fixture
async def app(test_db, monkeypatch):
    fake_redis = FakeRedis()
    dispatch_pipeline = MagicMock()
    rerender_task = SimpleNamespace(delay=MagicMock())

    monkeypatch.setattr(api_routes, "_redis", fake_redis)
    monkeypatch.setattr(worker_tasks, "_redis", fake_redis)
    monkeypatch.setattr(api_routes, "dispatch_pipeline", dispatch_pipeline)
    monkeypatch.setattr(worker_tasks, "task_rerender_video", rerender_task)
    monkeypatch.setattr(auth_routes, "send_verification_email", MagicMock(return_value=True))
    monkeypatch.setattr(auth_routes, "send_password_reset_email", MagicMock(return_value=True))
    monkeypatch.setattr(auth_routes, "send_account_deleted_email", MagicMock(return_value=True))

    app = create_app()
    app.dependency_overrides[get_db] = test_db["override_get_db"]
    app.state.fake_redis = fake_redis
    app.state.dispatch_pipeline = dispatch_pipeline
    app.state.rerender_task = rerender_task
    return app


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app, client=("127.0.0.1", 50000), raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


@pytest_asyncio.fixture
async def client_factory(app):
    clients = []

    @asynccontextmanager
    async def _make(ip: str = "127.0.0.1"):
        transport = ASGITransport(app=app, client=(ip, 50000), raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
            clients.append(async_client)
            yield async_client

    yield _make

    for async_client in clients:
        await async_client.aclose()


@pytest_asyncio.fixture
async def db_session(test_db):
    async with test_db["session_factory"]() as session:
        yield session


@pytest.fixture
def auth_headers():
    def _headers(user: User) -> dict[str, str]:
        return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}

    return _headers


@pytest_asyncio.fixture
async def user_factory(test_db):
    async def _create_user(
        *,
        email: str = "user@example.com",
        name: str = "Test User",
        password_hash: str = "hashed-password",
        credits: int = 0,
        plan: str = "free",
        verified: bool = False,
        verification_code: str | None = "123456",
        verification_expires=None,
    ) -> User:
        from datetime import datetime, timedelta, timezone

        if verification_expires is None and verification_code is not None:
            verification_expires = datetime.now(timezone.utc) + timedelta(minutes=10)

        async with test_db["session_factory"]() as session:
            user = User(
                email=email,
                name=name,
                password_hash=password_hash,
                credits=credits,
                plan=plan,
                email_verified=verified,
                verification_code=verification_code if not verified else None,
                verification_expires=verification_expires if not verified else None,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user

    return _create_user


@pytest_asyncio.fixture
async def verified_user(user_factory):
    from app.auth.service import hash_password

    return await user_factory(
        email="verified@example.com",
        password_hash=hash_password("supersecret"),
        credits=5,
        verified=True,
        verification_code=None,
        verification_expires=None,
    )


@pytest_asyncio.fixture
async def other_verified_user(user_factory):
    from app.auth.service import hash_password

    return await user_factory(
        email="other-verified@example.com",
        password_hash=hash_password("supersecret"),
        credits=5,
        verified=True,
        verification_code=None,
        verification_expires=None,
    )


@pytest_asyncio.fixture
async def admin_user(user_factory):
    from app.auth.service import hash_password

    return await user_factory(
        email="admin@example.com",
        name="Admin User",
        password_hash=hash_password("supersecret"),
        credits=10,
        plan="admin",
        verified=True,
        verification_code=None,
        verification_expires=None,
    )


@pytest_asyncio.fixture
async def unverified_user(user_factory):
    from app.auth.service import hash_password

    return await user_factory(
        email="pending@example.com",
        password_hash=hash_password("supersecret"),
        credits=0,
        verified=False,
    )


@pytest_asyncio.fixture
async def job_factory(test_db, verified_user):
    async def _create_job(
        *,
        user_id=None,
        status: str = "queued",
        pending_credits: float = 0.0,
        editor_state: dict | None = None,
        script: dict | None = None,
        template_id: str = "stock_narration",
    ) -> Job:
        async with test_db["session_factory"]() as session:
            job = Job(
                user_id=user_id or verified_user.id,
                topic="Topic",
                style="educational",
                duration_target=45,
                status=status,
                pending_credits=pending_credits,
                editor_state=editor_state,
                script=script,
                template_id=template_id,
            )
            session.add(job)
            await session.commit()
            await session.refresh(job)
            return job

    return _create_job


@pytest_asyncio.fixture
async def purchase_factory(test_db, verified_user):
    async def _create_purchase(
        *,
        user_id=None,
        package_name: str = "starter",
        status: str = "pending",
        provider: str = "mercadopago",
        mp_preference_id: str = "pref_123",
        mp_payment_id: str | None = None,
    ) -> CreditPurchase:
        pkg = CREDIT_PACKAGES[package_name]
        async with test_db["session_factory"]() as session:
            purchase = CreditPurchase(
                user_id=user_id or verified_user.id,
                package_name=package_name,
                credits_amount=pkg["credits"],
                price_brl=pkg["price_brl"],
                provider=provider,
                mp_preference_id=mp_preference_id,
                mp_payment_id=mp_payment_id,
                status=status,
            )
            session.add(purchase)
            await session.commit()
            await session.refresh(purchase)
            return purchase

    return _create_purchase


@pytest.fixture
def storage_dir(test_db) -> Path:
    return test_db["storage_dir"]


import base64  # noqa: E402 — appended after module-level imports


@pytest.fixture
def tiny_png_b64() -> str:
    """Minimal valid PNG bytes, base64-encoded — for mocking image API responses."""
    png_bytes = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x00\x03\x00\x01"
        b"\xc4[\x8d\x9a"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    return base64.b64encode(png_bytes).decode()
