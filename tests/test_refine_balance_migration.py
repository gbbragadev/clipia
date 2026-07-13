from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from sqlalchemy import Column, Integer, MetaData, Table, create_engine, inspect

from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_refine_balance_migration_upgrades_and_downgrades(monkeypatch):
    engine = create_engine("sqlite://")
    metadata = MetaData()
    Table("users", metadata, Column("id", Integer, primary_key=True))
    Table("jobs", metadata, Column("id", Integer, primary_key=True))

    with engine.begin() as connection:
        metadata.create_all(connection)
        migration_path = (
            Path(__file__).parents[1] / "alembic" / "versions" / "a7b8c9d0e1f2_persist_script_refine_balance.py"
        )
        spec = spec_from_file_location("persist_script_refine_balance", migration_path)
        assert spec is not None and spec.loader is not None
        migration = module_from_spec(spec)
        spec.loader.exec_module(migration)
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))

        migration.upgrade()

        assert {column["name"] for column in inspect(connection).get_columns("users")} == {
            "id",
            "script_refine_pending",
            "script_refine_redis_migrated",
        }
        assert {column["name"] for column in inspect(connection).get_columns("jobs")} == {
            "id",
            "refine_credit_cost",
        }

        migration.downgrade()

        assert {column["name"] for column in inspect(connection).get_columns("users")} == {"id"}
        assert {column["name"] for column in inspect(connection).get_columns("jobs")} == {"id"}
