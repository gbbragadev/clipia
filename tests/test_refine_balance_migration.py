import uuid
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, inspect, text

from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_refine_balance_migration_upgrades_and_downgrades(monkeypatch):
    engine = create_engine("sqlite://")
    metadata = MetaData()
    Table("users", metadata, Column("id", Integer, primary_key=True))
    Table("jobs", metadata, Column("id", Integer, primary_key=True))

    with engine.begin() as connection:
        metadata.create_all(connection)
        base_migration_path = (
            Path(__file__).parents[1] / "alembic" / "versions" / "a7b8c9d0e1f2_persist_script_refine_balance.py"
        )
        base_spec = spec_from_file_location("persist_script_refine_balance", base_migration_path)
        assert base_spec is not None and base_spec.loader is not None
        base_migration = module_from_spec(base_spec)
        base_spec.loader.exec_module(base_migration)
        monkeypatch.setattr(base_migration, "op", Operations(MigrationContext.configure(connection)))
        migration_path = (
            Path(__file__).parents[1] / "alembic" / "versions" / "b8c9d0e1f2a3_add_dispatch_and_refine_outboxes.py"
        )
        spec = spec_from_file_location("add_dispatch_and_refine_outboxes", migration_path)
        assert spec is not None and spec.loader is not None
        migration = module_from_spec(spec)
        spec.loader.exec_module(migration)
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))

        base_migration.upgrade()
        migration.upgrade()

        assert {column["name"] for column in inspect(connection).get_columns("users")} == {
            "id",
            "script_refine_pending",
            "script_refine_version",
            "script_refine_redis_migrated",
        }
        assert {column["name"] for column in inspect(connection).get_columns("jobs")} == {
            "id",
            "refine_credit_cost",
        }
        assert {"job_dispatches", "refine_balance_outbox"}.issubset(inspect(connection).get_table_names())
        dispatch_columns = {column["name"] for column in inspect(connection).get_columns("job_dispatches")}
        assert {
            "worker_heartbeat_at",
            "debited_credits",
            "refine_debited",
            "pending_credits_snapshot",
        }.issubset(dispatch_columns)

        connection.execute(text("INSERT INTO users (id) VALUES (1)"))
        connection.execute(
            text("INSERT INTO refine_balance_outbox (id, user_id, version, balance_after) VALUES (:id, 1, 1, 0.5)"),
            {"id": str(uuid.uuid4())},
        )

        with pytest.raises(RuntimeError, match="refine balance projections are pending"):
            migration.downgrade()

        connection.execute(text("UPDATE refine_balance_outbox SET applied_at = CURRENT_TIMESTAMP"))
        connection.execute(
            text("UPDATE users SET script_refine_pending = 0.5, script_refine_redis_migrated = 1 WHERE id = 1")
        )

        with pytest.raises(RuntimeError, match="authority has not been handed off"):
            migration.downgrade()

        connection.execute(
            text("UPDATE users SET script_refine_pending = 0, script_refine_redis_migrated = 0 WHERE id = 1")
        )

        migration.downgrade()
        base_migration.downgrade()

        assert {column["name"] for column in inspect(connection).get_columns("users")} == {"id"}
        assert {column["name"] for column in inspect(connection).get_columns("jobs")} == {"id"}
        assert "job_dispatches" not in inspect(connection).get_table_names()
        assert "refine_balance_outbox" not in inspect(connection).get_table_names()
