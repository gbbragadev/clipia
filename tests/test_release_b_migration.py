from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory


def _load_migration():
    migrations = list(Path("alembic/versions").glob("*_add_selected_package_intent.py"))
    assert len(migrations) == 1
    spec = spec_from_file_location("add_selected_package_intent", migrations[0])
    assert spec and spec.loader
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_selected_package_migration_is_expansive_successor_with_one_head(monkeypatch):
    migration = _load_migration()
    assert migration.down_revision == "d0e1f2a3b4c5"
    assert ScriptDirectory.from_config(Config("alembic.ini")).get_heads() == ["e8f9a0b1c2d3"]

    engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    sa.Table(
        "users",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("credits", sa.Integer(), nullable=False),
    )
    with engine.begin() as connection:
        metadata.create_all(connection)
        connection.execute(sa.text("INSERT INTO users (id, credits) VALUES (1, 77)"))
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))

        migration.upgrade()
        inspector = sa.inspect(connection)
        selected_package = {column["name"]: column for column in inspector.get_columns("users")}["selected_package"]
        assert selected_package["nullable"] is True
        checks = {check["name"]: check["sqltext"] for check in inspector.get_check_constraints("users")}
        assert "ck_users_selected_package" in checks
        assert "professional" in checks["ck_users_selected_package"]
        assert connection.execute(sa.text("SELECT credits FROM users WHERE id = 1")).scalar_one() == 77

        connection.execute(sa.text("UPDATE users SET selected_package = 'professional' WHERE id = 1"))
        migration.downgrade()
        assert "selected_package" not in {column["name"] for column in sa.inspect(connection).get_columns("users")}

        migration.upgrade()
        assert "selected_package" in {column["name"] for column in sa.inspect(connection).get_columns("users")}
