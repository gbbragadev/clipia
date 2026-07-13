#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path

from sqlalchemy import inspect, text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import settings, validate_production_settings  # noqa: E402
from app.db.engine import build_engine  # noqa: E402
from app.main import create_app  # noqa: E402
from app.redis_pool import get_redis  # noqa: E402


class CheckFailure(Exception):
    pass


def main() -> int:
    checks = [
        ("JWT secret", check_jwt_secret),
        ("CORS", check_cors),
        ("Production security", check_production_security),
        ("Database URL", check_database_url),
        ("Redis URL", check_redis_url),
        ("Error handlers", check_error_handlers),
        ("Protected routes", check_protected_routes),
        ("SQLAlchemy pool", check_engine_pool),
        ("Alembic files", check_alembic_files),
        ("Jobs index migration", check_jobs_index_migration),
        ("Database schema", check_database_schema),
        ("Legacy rerender drain", check_no_legacy_rerenders),
    ]

    failures: list[str] = []
    for label, fn in checks:
        try:
            fn()
            print(f"[OK] {label}")
        except Exception as exc:
            failures.append(f"{label}: {exc}")
            print(f"[FAIL] {label}: {exc}")

    if failures:
        print("\nPredeploy check failed.")
        return 1

    print("\nPredeploy check passed.")
    return 0


def check_jwt_secret() -> None:
    if settings.JWT_SECRET == "dev-secret-change-in-production":
        raise CheckFailure("JWT_SECRET ainda está no valor padrão.")


def check_cors() -> None:
    if settings.CORS_ORIGINS.strip() == "*":
        raise CheckFailure("CORS_ORIGINS não pode ser '*'.")


def check_production_security() -> None:
    if settings.ENVIRONMENT != "production":
        raise CheckFailure("ENVIRONMENT deve ser 'production' no gate de deploy.")
    validate_production_settings(settings)


def check_database_url() -> None:
    if not settings.DATABASE_URL:
        raise CheckFailure("DATABASE_URL não configurada.")


def check_redis_url() -> None:
    if not settings.REDIS_URL:
        raise CheckFailure("REDIS_URL não configurada.")


def check_error_handlers() -> None:
    app = create_app()
    handlers = app.exception_handlers
    if Exception not in handlers:
        raise CheckFailure("Handler global de 500 não registrado.")


def check_protected_routes() -> None:
    api_routes = importlib.import_module("app.api.routes")
    protected_paths = {
        "/jobs/{job_id}",
        "/jobs/{job_id}/download",
        "/jobs/{job_id}/composition",
        "/admin/storage-stats",
    }
    route_map = {route.path: route for route in api_routes.router.routes}
    for path in protected_paths:
        route = route_map.get(path)
        if route is None:
            raise CheckFailure(f"Rota ausente: {path}")
        if not route.dependant.dependencies:
            raise CheckFailure(f"Rota sem dependências de auth: {path}")


def check_engine_pool() -> None:
    engine = build_engine(settings.DATABASE_URL)
    try:
        if "sqlite" in settings.DATABASE_URL:
            return
        pool = engine.sync_engine.pool
        if pool.size() <= 0:
            raise CheckFailure("Pool sem tamanho configurado.")
    finally:
        asyncio.run(engine.dispose())


def check_alembic_files() -> None:
    versions_dir = ROOT / "alembic" / "versions"
    if not versions_dir.exists():
        raise CheckFailure("Diretório de migrations não encontrado.")
    if not any(versions_dir.glob("*.py")):
        raise CheckFailure("Nenhuma migration encontrada.")


def check_jobs_index_migration() -> None:
    migration_path = ROOT / "alembic" / "versions" / "f2b6c6a9d51b_add_jobs_user_id_index.py"
    if not migration_path.exists():
        raise CheckFailure("Migration do índice jobs.user_id não encontrada.")


def check_database_schema() -> None:
    asyncio.run(_check_database_schema_async())


def check_no_legacy_rerenders() -> None:
    """Block a worker cutover while Redis-only rerenders can still be redelivered."""
    database_ids = asyncio.run(_active_legacy_rerender_ids())
    redis_ids: set[str] = set()
    redis_client = get_redis()
    try:
        for raw_key in redis_client.scan_iter(match="job:*", count=200):
            key = raw_key.decode() if isinstance(raw_key, bytes) else str(raw_key)
            if key.endswith(":cancelled"):
                continue
            live = redis_client.hgetall(key)
            operation_id = live.get("rerender_operation_id") or live.get(b"rerender_operation_id")
            raw_cost = live.get("rerender_cost") or live.get(b"rerender_cost")
            try:
                cost = int(float(raw_cost)) if raw_cost else 0
            except (TypeError, ValueError):
                cost = 0
            if cost > 0 and not operation_id:
                redis_ids.add(key.removeprefix("job:"))
    finally:
        redis_client.close()

    blocked = sorted(database_ids | redis_ids)
    if blocked:
        sample = ", ".join(blocked[:10])
        raise CheckFailure(
            f"rerenders legados ativos; drene/terminalize antes de trocar workers (total={len(blocked)}, jobs={sample})"
        )


async def _active_legacy_rerender_ids() -> set[str]:
    engine = build_engine(settings.DATABASE_URL)
    try:
        async with engine.connect() as conn:
            rows = await conn.execute(
                text(
                    "SELECT id FROM jobs WHERE rerender_operation_id IS NULL "
                    "AND rerender_state IN ('debited', 'dispatched', 'running')"
                )
            )
            return {str(row[0]) for row in rows}
    finally:
        await engine.dispose()


async def _check_database_schema_async() -> None:
    engine = build_engine(settings.DATABASE_URL)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

            def _read_indexes(sync_conn):
                inspector = inspect(sync_conn)
                return {idx["name"] for idx in inspector.get_indexes("jobs")}

            indexes = await conn.run_sync(_read_indexes)
            if "ix_jobs_user_id" not in indexes:
                raise CheckFailure("Índice ix_jobs_user_id ausente no banco.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
