import uuid
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def _load_migration():
    paths = list(Path("alembic/versions").glob("*_add_purchase_refunded_at.py"))
    assert len(paths) == 1
    spec = spec_from_file_location("add_purchase_refunded_at", paths[0])
    assert spec and spec.loader
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_refunded_at_migration_backfills_and_round_trips_on_sqlite(monkeypatch):
    migration = _load_migration()
    assert migration.down_revision == "c6d7e8f9a0b1"
    engine = sa.create_engine("sqlite:///:memory:")
    referrer_id = uuid.uuid4()
    referred_ids = [uuid.uuid4() for _ in range(11)]

    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "CREATE TABLE users (id TEXT PRIMARY KEY, referred_by TEXT, "
                "email_verified BOOLEAN NOT NULL DEFAULT 0, created_at DATETIME NOT NULL)"
            )
        )
        connection.execute(
            sa.text(
                "CREATE TABLE credit_ledger_entries (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, "
                "origin TEXT NOT NULL, idempotency_key TEXT NOT NULL, created_at DATETIME NOT NULL)"
            )
        )
        connection.execute(
            sa.text(
                "CREATE TABLE credit_purchases ("
                "id TEXT PRIMARY KEY, status TEXT NOT NULL, payment_state TEXT, "
                "created_at DATETIME NOT NULL, paid_at DATETIME)"
            )
        )
        connection.execute(sa.text("CREATE TABLE jobs (id TEXT PRIMARY KEY)"))
        connection.execute(
            sa.text(
                "INSERT INTO users (id, referred_by, email_verified, created_at) " "VALUES (:id, NULL, 1, '2026-06-01')"
            ),
            {"id": str(referrer_id)},
        )
        for index, referred_id in enumerate(referred_ids):
            connection.execute(
                sa.text(
                    "INSERT INTO users (id, referred_by, email_verified, created_at) "
                    "VALUES (:id, :referrer_id, 1, :created_at)"
                ),
                {
                    "id": str(referred_id),
                    "referrer_id": str(referrer_id),
                    "created_at": f"2026-06-{index + 2:02d}",
                },
            )
        ledger_backed_ids = referred_ids[1:]
        for index, referred_id in enumerate(ledger_backed_ids):
            connection.execute(
                sa.text(
                    "INSERT INTO credit_ledger_entries "
                    "(id, user_id, origin, idempotency_key, created_at) "
                    "VALUES (:id, :user_id, 'referral_bonus', :idempotency_key, :created_at)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "user_id": str(referrer_id),
                    "idempotency_key": f"referral:{referred_id}",
                    "created_at": f"2026-06-{index + 2:02d}",
                },
            )
        connection.execute(
            sa.text(
                "INSERT INTO credit_purchases "
                "(id, status, payment_state, created_at, paid_at) VALUES "
                "('refund-before-paid', 'refunded', 'refunded', '2026-07-01', NULL), "
                "('paid-refund', 'refunded', 'refunded', '2026-07-01', '2026-07-02')"
            )
        )
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))

        migration.upgrade()
        inspector = sa.inspect(connection)
        assert "refunded_at" in {column["name"] for column in inspector.get_columns("credit_purchases")}
        assert "ix_credit_purchases_refunded_at" in {
            index["name"] for index in inspector.get_indexes("credit_purchases")
        }
        assert "legacy_rerender_task_id" in {column["name"] for column in inspector.get_columns("jobs")}
        assert "referral_credit_awards" in inspector.get_table_names()
        legacy_awards = (
            connection.execute(
                sa.text(
                    "SELECT referred_user_id FROM referral_credit_awards "
                    "WHERE referrer_user_id = :referrer_id ORDER BY referred_user_id"
                ),
                {"referrer_id": referrer_id.hex},
            )
            .scalars()
            .all()
        )
        assert len(legacy_awards) == 10
        assert referred_ids[0].hex not in legacy_awards
        assert referred_ids[10].hex in legacy_awards
        rows = connection.execute(sa.text("SELECT id, refunded_at FROM credit_purchases ORDER BY id")).all()
        assert all(row.refunded_at is not None for row in rows)

        migration.downgrade()
        assert "refunded_at" not in {
            column["name"] for column in sa.inspect(connection).get_columns("credit_purchases")
        }
        assert "legacy_rerender_task_id" not in {
            column["name"] for column in sa.inspect(connection).get_columns("jobs")
        }
        assert "referral_credit_awards" not in sa.inspect(connection).get_table_names()
