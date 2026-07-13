from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory


def _load_migration():
    migrations = list(Path("alembic/versions").glob("*_add_append_only_analytics_events.py"))
    assert len(migrations) == 1
    spec = spec_from_file_location("add_append_only_analytics_events", migrations[0])
    assert spec and spec.loader
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def _insert_event(connection, event_id: str) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO analytics_events ("
            "event_id, event_name, schema_version, authority, occurred_at, anonymous_session_id, "
            "page, acquisition_source, device_class, properties, payload_hash"
            ") VALUES ("
            ":event_id, 'landing_viewed', 1, 'client', CURRENT_TIMESTAMP, NULL, "
            "'landing', 'direct', 'desktop', '{}', :payload_hash"
            ")"
        ),
        {"event_id": event_id, "payload_hash": "a" * 64},
    )


def test_analytics_migration_is_single_head_and_append_only_on_sqlite(monkeypatch):
    migration = _load_migration()
    assert migration.down_revision == "e1f2a3b4c5d6"
    assert ScriptDirectory.from_config(Config("alembic.ini")).get_heads() == ["d7e8f9a0b1c2"]

    engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    sa.Table("users", metadata, sa.Column("id", sa.UUID(), primary_key=True))
    with engine.begin() as connection:
        metadata.create_all(connection)
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))

        migration.upgrade()
        inspector = sa.inspect(connection)
        columns = {column["name"] for column in inspector.get_columns("analytics_events")}
        indexes = {index["name"] for index in inspector.get_indexes("analytics_events")}
        assert {"event_id", "event_name", "user_id", "properties", "payload_hash"} <= columns
        assert {
            "ix_analytics_events_event_time",
            "ix_analytics_events_session_time",
            "ix_analytics_events_user_time",
            "ix_analytics_events_event_user_time",
        } <= indexes

        event_id = "00000000-0000-4000-8000-000000000001"
        _insert_event(connection, event_id)
        with pytest.raises(sa.exc.DatabaseError, match="append-only"):
            connection.execute(
                sa.text("UPDATE analytics_events SET page = 'blog' WHERE event_id = :event_id"),
                {"event_id": event_id},
            )
        with pytest.raises(sa.exc.DatabaseError, match="append-only"):
            connection.execute(
                sa.text("DELETE FROM analytics_events WHERE event_id = :event_id"),
                {"event_id": event_id},
            )

        migration.downgrade()
        assert "analytics_events" not in sa.inspect(connection).get_table_names()
        migration.upgrade()
        assert "analytics_events" in sa.inspect(connection).get_table_names()
