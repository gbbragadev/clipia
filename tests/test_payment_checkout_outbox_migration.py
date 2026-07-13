from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory


def _load_migration():
    migrations = list(Path("alembic/versions").glob("*_add_payment_checkout_outbox.py"))
    assert len(migrations) == 1
    spec = spec_from_file_location("add_payment_checkout_outbox", migrations[0])
    assert spec and spec.loader
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_payment_checkout_outbox_migration_has_one_head_and_sqlite_structure(monkeypatch):
    migration = _load_migration()
    assert migration.down_revision == "c9d0e1f2a3b4"
    assert ScriptDirectory.from_config(Config("alembic.ini")).get_revision(migration.revision) is not None

    engine = sa.create_engine("sqlite:///:memory:")
    metadata = sa.MetaData()
    sa.Table("users", metadata, sa.Column("id", sa.String(36), primary_key=True))
    sa.Table("credit_purchases", metadata, sa.Column("id", sa.String(36), primary_key=True))
    with engine.begin() as connection:
        metadata.create_all(connection)
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()

        inspector = sa.inspect(connection)
        columns = {column["name"]: column for column in inspector.get_columns("payment_checkout_dispatches")}
        assert {
            "id",
            "purchase_id",
            "user_id",
            "provider",
            "provider_idempotency_key",
            "request_key",
            "request_fingerprint",
            "request_payload",
            "request_payload_hash",
            "state",
            "attempt_count",
            "next_attempt_at",
            "last_attempt_at",
            "publisher_token",
            "publisher_lease_until",
            "provider_checkout_id",
            "checkout_url",
            "checkout_expires_at",
            "error_code",
            "error_detail",
            "created_at",
            "ready_at",
            "failed_at",
        } == set(columns)
        assert columns["request_payload"]["type"].__class__.__name__ == "TEXT"

        foreign_keys = {
            tuple(fk["constrained_columns"]): fk for fk in inspector.get_foreign_keys("payment_checkout_dispatches")
        }
        assert foreign_keys[("purchase_id",)]["referred_table"] == "credit_purchases"
        assert foreign_keys[("purchase_id",)]["options"]["ondelete"] == "RESTRICT"
        assert foreign_keys[("user_id",)]["referred_table"] == "users"
        assert foreign_keys[("user_id",)]["options"]["ondelete"] == "RESTRICT"

        unique_columns = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints("payment_checkout_dispatches")
        }
        assert ("purchase_id",) in unique_columns
        assert ("provider_idempotency_key",) in unique_columns
        assert ("request_key",) in unique_columns
        index_names = {index["name"] for index in inspector.get_indexes("payment_checkout_dispatches")}
        assert "ix_payment_checkout_dispatch_due" in index_names
        assert "uq_payment_checkout_dispatch_provider_checkout" in index_names
        check_names = {check["name"] for check in inspector.get_check_constraints("payment_checkout_dispatches")}
        assert {
            "ck_payment_checkout_dispatch_provider",
            "ck_payment_checkout_dispatch_state",
            "ck_payment_checkout_dispatch_attempts",
            "ck_payment_checkout_dispatch_payload_hash",
            "ck_payment_checkout_dispatch_lease_pair",
            "ck_payment_checkout_dispatch_terminal_fields",
        } <= check_names

        migration.downgrade()
        assert "payment_checkout_dispatches" not in inspector.get_table_names()
