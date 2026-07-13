from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
import sqlalchemy as sa

from alembic.migration import MigrationContext
from alembic.operations import Operations


def _load_migration():
    migrations = list(Path("alembic/versions").glob("*_add_canonical_payment_state.py"))
    assert len(migrations) == 1
    spec = spec_from_file_location("add_canonical_payment_state", migrations[0])
    assert spec and spec.loader
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def _legacy_table(connection):
    metadata = sa.MetaData()
    table = sa.Table(
        "credit_purchases",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("mp_preference_id", sa.String(255), nullable=False),
        sa.Column("mp_payment_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("credits_amount", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("bonus_credits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("price_brl", sa.Integer(), nullable=False, server_default="1990"),
    )
    metadata.create_all(connection)
    return table


def test_payment_state_migration_backfills_without_rewriting_legacy_status(monkeypatch):
    engine = sa.create_engine("sqlite:///:memory:")
    migration = _load_migration()
    rows = [
        ("1", "approved", "paid"),
        ("2", "paid", "paid"),
        ("3", "pending", "pending"),
        ("4", "refunded", "refunded"),
        ("5", "cancelled", "void"),
        ("6", "rejected", "void"),
        ("7", "expired", "void"),
    ]

    with engine.begin() as connection:
        table = _legacy_table(connection)
        connection.execute(
            table.insert(),
            [
                {
                    "id": row_id,
                    "provider": "stripe" if row_id != "6" else "mercadopago",
                    "mp_preference_id": f"checkout_{row_id}",
                    "mp_payment_id": None,
                    "status": legacy,
                }
                for row_id, legacy, _canonical in rows
            ],
        )
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))

        migration.upgrade()

        reflected = sa.Table("credit_purchases", sa.MetaData(), autoload_with=connection)
        stored = connection.execute(
            sa.select(reflected.c.id, reflected.c.status, reflected.c.payment_state).order_by(reflected.c.id)
        ).all()
        assert stored == [(row_id, legacy, canonical) for row_id, legacy, canonical in rows]
        assert reflected.c.payment_state.nullable is True
        assert any(index["unique"] for index in sa.inspect(connection).get_indexes("credit_purchases"))

        migration.downgrade()
        downgraded_column_names = {column["name"] for column in sa.inspect(connection).get_columns("credit_purchases")}
        assert {"payment_state", "currency", "snapshot_version", "snapshot_hash"}.isdisjoint(downgraded_column_names)


def test_payment_state_migration_fails_on_unknown_legacy_status(monkeypatch):
    engine = sa.create_engine("sqlite:///:memory:")
    migration = _load_migration()

    with engine.begin() as connection:
        table = _legacy_table(connection)
        connection.execute(
            table.insert(),
            {
                "id": "1",
                "provider": "stripe",
                "mp_preference_id": "checkout_1",
                "mp_payment_id": None,
                "status": "mystery",
            },
        )
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))

        with pytest.raises(RuntimeError, match="Unknown legacy credit purchase statuses: mystery"):
            migration.upgrade()


@pytest.mark.parametrize("identity", ["checkout", "payment"])
def test_payment_state_migration_rejects_real_provider_identity_duplicates(monkeypatch, identity):
    engine = sa.create_engine("sqlite:///:memory:")
    migration = _load_migration()

    with engine.begin() as connection:
        table = _legacy_table(connection)
        rows = []
        for row_id in ("1", "2"):
            rows.append(
                {
                    "id": row_id,
                    "provider": "stripe",
                    "mp_preference_id": "cs_duplicate" if identity == "checkout" else f"cs_{row_id}",
                    "mp_payment_id": "pi_duplicate" if identity == "payment" else None,
                    "status": "pending",
                }
            )
        connection.execute(table.insert(), rows)
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))

        with pytest.raises(RuntimeError, match="Duplicate provider"):
            migration.upgrade()


def test_payment_state_migration_tolerates_pending_and_null_checkout_sentinels(monkeypatch):
    engine = sa.create_engine("sqlite:///:memory:")
    migration = _load_migration()

    with engine.begin() as connection:
        table = _legacy_table(connection)
        connection.execute(
            table.insert(),
            [
                {
                    "id": str(index),
                    "provider": "stripe",
                    "mp_preference_id": "pending",
                    "mp_payment_id": None,
                    "status": "pending",
                }
                for index in range(1, 4)
            ],
        )
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))

        migration.upgrade()

        reflected = sa.Table("credit_purchases", sa.MetaData(), autoload_with=connection)
        connection.execute(
            reflected.insert(),
            {
                "id": "4",
                "provider": "stripe",
                "mp_preference_id": None,
                "mp_payment_id": None,
                "status": "pending",
                "payment_state": "pending",
                "credits_amount": 10,
                "bonus_credits": 0,
                "price_brl": 1990,
            },
        )


def test_payment_state_downgrade_materializes_precedence_and_round_trips(monkeypatch):
    engine = sa.create_engine("sqlite:///:memory:")
    migration = _load_migration()
    divergent_rows = [
        ("1", "approved", "refunded", "refunded"),
        ("2", "refunded", "paid", "refunded"),
        ("3", "pending", "paid", "approved"),
        ("4", "approved", "void", "approved"),
        ("5", "pending", "void", "pending"),
    ]

    with engine.begin() as connection:
        table = _legacy_table(connection)
        connection.execute(
            table.insert(),
            [
                {
                    "id": row_id,
                    "provider": "stripe",
                    "mp_preference_id": f"checkout_{row_id}",
                    "mp_payment_id": None,
                    "status": legacy_status,
                }
                for row_id, legacy_status, _payment_state, _expected_status in divergent_rows
            ],
        )
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()

        canonical_table = sa.Table("credit_purchases", sa.MetaData(), autoload_with=connection)
        for row_id, _legacy_status, payment_state, _expected_status in divergent_rows:
            connection.execute(
                canonical_table.update().where(canonical_table.c.id == row_id).values(payment_state=payment_state)
            )

        migration.downgrade()

        legacy_table = sa.Table("credit_purchases", sa.MetaData(), autoload_with=connection)
        downgraded = connection.execute(
            sa.select(legacy_table.c.id, legacy_table.c.status).order_by(legacy_table.c.id)
        ).all()
        assert downgraded == [(row_id, expected_status) for row_id, _legacy, _state, expected_status in divergent_rows]
        downgraded_column_names = {column["name"] for column in sa.inspect(connection).get_columns("credit_purchases")}
        assert {"payment_state", "currency", "snapshot_version", "snapshot_hash"}.isdisjoint(downgraded_column_names)

        migration.upgrade()
        round_trip_table = sa.Table("credit_purchases", sa.MetaData(), autoload_with=connection)
        round_trip = connection.execute(
            sa.select(round_trip_table.c.id, round_trip_table.c.status, round_trip_table.c.payment_state).order_by(
                round_trip_table.c.id
            )
        ).all()
        assert round_trip == [
            ("1", "refunded", "refunded"),
            ("2", "refunded", "refunded"),
            ("3", "approved", "paid"),
            ("4", "approved", "paid"),
            ("5", "pending", "pending"),
        ]
