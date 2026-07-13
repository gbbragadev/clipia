"""add canonical payment state and immutable checkout snapshot

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: str | None = "b8c9d0e1f2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_KNOWN_LEGACY = (
    "pending",
    "approved",
    "paid",
    "refunded",
    "charged_back",
    "cancelled",
    "canceled",
    "rejected",
    "expired",
    "void",
)


def _preflight(connection) -> None:
    placeholders = ", ".join(f"'{value}'" for value in _KNOWN_LEGACY)
    unknown = (
        connection.execute(
            sa.text(
                "SELECT DISTINCT status FROM credit_purchases "
                f"WHERE status IS NULL OR LOWER(status) NOT IN ({placeholders}) "
                "ORDER BY status"
            )
        )
        .scalars()
        .all()
    )
    if unknown:
        rendered = ", ".join("NULL" if value is None else str(value) for value in unknown)
        raise RuntimeError(f"Unknown legacy credit purchase statuses: {rendered}")

    duplicate_checkouts = connection.execute(
        sa.text(
            "SELECT provider, mp_preference_id, COUNT(*) AS n FROM credit_purchases "
            "WHERE mp_preference_id IS NOT NULL AND mp_preference_id <> 'pending' "
            "GROUP BY provider, mp_preference_id HAVING COUNT(*) > 1"
        )
    ).all()
    if duplicate_checkouts:
        raise RuntimeError("Duplicate provider checkout identities prevent payment-state migration")

    duplicate_payments = connection.execute(
        sa.text(
            "SELECT provider, mp_payment_id, COUNT(*) AS n FROM credit_purchases "
            "WHERE mp_payment_id IS NOT NULL "
            "GROUP BY provider, mp_payment_id HAVING COUNT(*) > 1"
        )
    ).all()
    if duplicate_payments:
        raise RuntimeError("Duplicate provider payment identities prevent payment-state migration")


def upgrade() -> None:
    connection = op.get_bind()
    _preflight(connection)

    with op.batch_alter_table("credit_purchases") as batch_op:
        batch_op.alter_column("mp_preference_id", existing_type=sa.String(length=255), nullable=True)
        batch_op.add_column(sa.Column("payment_state", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("currency", sa.String(length=3), server_default="BRL", nullable=False))
        batch_op.add_column(sa.Column("snapshot_version", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("snapshot_hash", sa.String(length=64), nullable=True))

    connection.execute(
        sa.text(
            "UPDATE credit_purchases SET payment_state = CASE "
            "WHEN LOWER(status) IN ('refunded', 'charged_back') THEN 'refunded' "
            "WHEN LOWER(status) IN ('approved', 'paid') THEN 'paid' "
            "WHEN LOWER(status) IN ('cancelled', 'canceled', 'rejected', 'expired', 'void') THEN 'void' "
            "ELSE 'pending' END"
        )
    )

    with op.batch_alter_table("credit_purchases") as batch_op:
        batch_op.create_check_constraint(
            "ck_credit_purchase_legacy_status",
            "status IN ('pending', 'approved', 'paid', 'refunded', 'charged_back', "
            "'cancelled', 'canceled', 'rejected', 'expired', 'void')",
        )
        batch_op.create_check_constraint("ck_credit_purchase_credits_positive", "credits_amount > 0")
        batch_op.create_check_constraint("ck_credit_purchase_bonus_nonnegative", "bonus_credits >= 0")
        batch_op.create_check_constraint("ck_credit_purchase_price_positive", "price_brl > 0")
        batch_op.create_check_constraint(
            "ck_credit_purchase_payment_state",
            "payment_state IS NULL OR payment_state IN ('pending', 'paid', 'refunded', 'void')",
        )
        batch_op.create_check_constraint(
            "ck_credit_purchase_snapshot_version",
            "snapshot_version IS NULL OR snapshot_version = 1",
        )
        batch_op.create_check_constraint(
            "ck_credit_purchase_snapshot_pair",
            "(snapshot_version IS NULL AND snapshot_hash IS NULL) OR "
            "(snapshot_version = 1 AND snapshot_hash IS NOT NULL AND LENGTH(snapshot_hash) = 64)",
        )

    op.create_index(
        "uq_credit_purchase_provider_checkout",
        "credit_purchases",
        ["provider", "mp_preference_id"],
        unique=True,
        postgresql_where=sa.text("mp_preference_id IS NOT NULL AND mp_preference_id <> 'pending'"),
        sqlite_where=sa.text("mp_preference_id IS NOT NULL AND mp_preference_id <> 'pending'"),
    )
    op.create_index(
        "uq_credit_purchase_provider_payment",
        "credit_purchases",
        ["provider", "mp_payment_id"],
        unique=True,
        postgresql_where=sa.text("mp_payment_id IS NOT NULL"),
        sqlite_where=sa.text("mp_payment_id IS NOT NULL"),
    )


def downgrade() -> None:
    connection = op.get_bind()
    # Preserve the strongest state old binaries can represent before removing
    # payment_state. Canonical void intentionally maps to pending because the
    # legacy constraint has no void value and a late paid event remains valid.
    connection.execute(
        sa.text(
            "UPDATE credit_purchases SET status = CASE "
            "WHEN LOWER(status) IN ('refunded', 'charged_back') OR payment_state = 'refunded' THEN 'refunded' "
            "WHEN LOWER(status) IN ('approved', 'paid') OR payment_state = 'paid' THEN 'approved' "
            "ELSE 'pending' END"
        )
    )
    op.drop_index("uq_credit_purchase_provider_payment", table_name="credit_purchases")
    op.drop_index("uq_credit_purchase_provider_checkout", table_name="credit_purchases")
    with op.batch_alter_table("credit_purchases") as batch_op:
        batch_op.drop_constraint("ck_credit_purchase_snapshot_pair", type_="check")
        batch_op.drop_constraint("ck_credit_purchase_snapshot_version", type_="check")
        batch_op.drop_constraint("ck_credit_purchase_payment_state", type_="check")
        batch_op.drop_constraint("ck_credit_purchase_legacy_status", type_="check")
        batch_op.drop_constraint("ck_credit_purchase_price_positive", type_="check")
        batch_op.drop_constraint("ck_credit_purchase_bonus_nonnegative", type_="check")
        batch_op.drop_constraint("ck_credit_purchase_credits_positive", type_="check")
        batch_op.drop_column("snapshot_hash")
        batch_op.drop_column("snapshot_version")
        batch_op.drop_column("currency")
        batch_op.drop_column("payment_state")
    connection.execute(
        sa.text("UPDATE credit_purchases SET mp_preference_id = 'pending' WHERE mp_preference_id IS NULL")
    )
    with op.batch_alter_table("credit_purchases") as batch_op:
        batch_op.alter_column("mp_preference_id", existing_type=sa.String(length=255), nullable=False)
