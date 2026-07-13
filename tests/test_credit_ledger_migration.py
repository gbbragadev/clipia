from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory


def _load_migration():
    migrations = list(Path("alembic/versions").glob("*_add_shadow_credit_ledger.py"))
    assert len(migrations) == 1
    spec = spec_from_file_location("add_shadow_credit_ledger", migrations[0])
    assert spec and spec.loader
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_credit_ledger_migration_backfills_projects_and_is_append_only_on_sqlite(monkeypatch):
    migration = _load_migration()
    assert migration.down_revision == "a4b5c6d7e8f9"
    assert ScriptDirectory.from_config(Config("alembic.ini")).get_heads() == ["d7e8f9a0b1c2"]

    engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    sa.Table(
        "users",
        metadata,
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("credits", sa.Integer(), nullable=False),
    )
    user_id = "11111111-1111-4111-8111-111111111111"
    with engine.begin() as connection:
        metadata.create_all(connection)
        connection.execute(
            sa.text("INSERT INTO users (id, credits) VALUES (:id, 7)"),
            {"id": user_id},
        )
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))

        migration.upgrade()
        inspector = sa.inspect(connection)
        assert {
            "credit_ledger_entries",
            "credit_ledger_reconciliation_runs",
        } <= set(inspector.get_table_names())

        backfill = connection.execute(
            sa.text("SELECT delta, origin, balance_after FROM credit_ledger_entries WHERE user_id = :user_id"),
            {"user_id": user_id},
        ).one()
        assert backfill == (7, "backfill", 7)

        connection.execute(
            sa.text("UPDATE users SET credits = credits + 3 WHERE id = :user_id"),
            {"user_id": user_id},
        )
        projected = connection.execute(
            sa.text("SELECT SUM(delta), MAX(balance_after) FROM credit_ledger_entries WHERE user_id = :user_id"),
            {"user_id": user_id},
        ).one()
        assert projected == (10, 10)

        with pytest.raises(sa.exc.DatabaseError, match="append-only"):
            connection.execute(sa.text("UPDATE credit_ledger_entries SET reason = 'tampered'"))
        with pytest.raises(sa.exc.DatabaseError, match="append-only"):
            connection.execute(sa.text("DELETE FROM credit_ledger_entries"))

        migration.downgrade()
        assert "credit_ledger_entries" not in sa.inspect(connection).get_table_names()
        migration.upgrade()
        assert connection.execute(sa.text("SELECT SUM(delta) FROM credit_ledger_entries")).scalar_one() == 10
