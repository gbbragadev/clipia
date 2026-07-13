from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def _load(pattern: str, name: str):
    paths = list(Path("alembic/versions").glob(pattern))
    assert len(paths) == 1
    spec = spec_from_file_location(name, paths[0])
    assert spec and spec.loader
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def _insert(connection, event_id: str, event_name: str, authority: str) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO analytics_events ("
            "event_id, event_name, schema_version, authority, occurred_at, anonymous_session_id, "
            "page, acquisition_source, device_class, properties, payload_hash"
            ") VALUES ("
            ":event_id, :event_name, 1, :authority, CURRENT_TIMESTAMP, NULL, "
            "'dashboard', 'direct', 'unknown', '{}', :payload_hash"
            ")"
        ),
        {
            "event_id": event_id,
            "event_name": event_name,
            "authority": authority,
            "payload_hash": event_id.replace("-", "") * 2,
        },
    )


def test_catalog_migration_expands_constraint_and_preserves_append_only(monkeypatch):
    initial = _load("*_add_append_only_analytics_events.py", "initial_analytics")
    catalog = _load("*_expand_analytics_event_catalog.py", "expanded_analytics")
    assert catalog.down_revision == "b5c6d7e8f9a0"

    engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    sa.Table("users", metadata, sa.Column("id", sa.UUID(), primary_key=True))
    with engine.begin() as connection:
        metadata.create_all(connection)
        operations = Operations(MigrationContext.configure(connection))
        monkeypatch.setattr(initial, "op", operations)
        monkeypatch.setattr(catalog, "op", operations)
        initial.upgrade()

        with pytest.raises(sa.exc.IntegrityError):
            _insert(connection, "00000000-0000-4000-8000-000000000011", "user_registered", "server")

        catalog.upgrade()
        _insert(connection, "00000000-0000-4000-8000-000000000012", "user_registered", "server")
        _insert(connection, "00000000-0000-4000-8000-000000000013", "editor_opened", "client")
        with pytest.raises(sa.exc.IntegrityError):
            _insert(connection, "00000000-0000-4000-8000-000000000014", "unknown", "server")
        with pytest.raises(sa.exc.DatabaseError, match="append-only"):
            connection.execute(sa.text("UPDATE analytics_events SET page = 'editor'"))
