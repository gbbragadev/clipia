from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory


def _load_migration():
    migrations = list(Path("alembic/versions").glob("*_add_one_time_reset_and_consent_versions.py"))
    assert len(migrations) == 1
    spec = spec_from_file_location("add_auth_hardening", migrations[0])
    assert spec and spec.loader
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_auth_hardening_migration_is_expansive_and_round_trips_on_sqlite(monkeypatch):
    migration = _load_migration()
    assert migration.down_revision == "f3a4b5c6d7e8"
    assert ScriptDirectory.from_config(Config("alembic.ini")).get_heads() == ["e8f9a0b1c2d3"]

    engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    sa.Table(
        "users",
        metadata,
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("credits", sa.Integer(), nullable=False),
    )
    with engine.begin() as connection:
        metadata.create_all(connection)
        connection.execute(
            sa.text("INSERT INTO users (id, credits) VALUES (:id, 77)"),
            {"id": "11111111-1111-4111-8111-111111111111"},
        )
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))

        migration.upgrade()
        inspector = sa.inspect(connection)
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        assert {"consent_terms_version", "consent_privacy_version"} <= user_columns
        assert "password_reset_tokens" in inspector.get_table_names()
        assert connection.execute(sa.text("SELECT credits FROM users")).scalar_one() == 77
        assert connection.execute(sa.text("SELECT consent_terms_version FROM users")).scalar_one() is None

        migration.downgrade()
        inspector = sa.inspect(connection)
        assert "password_reset_tokens" not in inspector.get_table_names()
        assert "consent_terms_version" not in {column["name"] for column in inspector.get_columns("users")}

        migration.upgrade()
        assert "password_reset_tokens" in sa.inspect(connection).get_table_names()
