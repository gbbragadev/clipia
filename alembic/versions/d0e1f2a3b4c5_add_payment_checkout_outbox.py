"""add crash-safe payment checkout outbox

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d0e1f2a3b4c5"
down_revision: str | None = "c9d0e1f2a3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "payment_checkout_dispatches",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "purchase_id",
            sa.UUID(),
            sa.ForeignKey("credit_purchases.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("provider_idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("request_key", sa.String(length=64), nullable=True),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("request_payload", sa.Text(), nullable=False),
        sa.Column("request_payload_hash", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("publisher_token", sa.UUID(), nullable=True),
        sa.Column("publisher_lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_checkout_id", sa.String(length=255), nullable=True),
        sa.Column("checkout_url", sa.Text(), nullable=True),
        sa.Column("checkout_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=40), nullable=True),
        sa.Column("error_detail", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("purchase_id", name="uq_payment_checkout_dispatch_purchase"),
        sa.UniqueConstraint(
            "provider_idempotency_key",
            name="uq_payment_checkout_dispatch_provider_key",
        ),
        sa.UniqueConstraint("request_key", name="uq_payment_checkout_dispatch_request_key"),
        sa.CheckConstraint(
            "provider IN ('stripe', 'mercadopago')",
            name="ck_payment_checkout_dispatch_provider",
        ),
        sa.CheckConstraint(
            "state IN ('pending', 'ready', 'failed', 'cancelled')",
            name="ck_payment_checkout_dispatch_state",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_payment_checkout_dispatch_attempts"),
        sa.CheckConstraint(
            "LENGTH(request_payload_hash) = 64",
            name="ck_payment_checkout_dispatch_payload_hash",
        ),
        sa.CheckConstraint(
            "request_key IS NULL OR LENGTH(request_key) = 64",
            name="ck_payment_checkout_dispatch_request_key",
        ),
        sa.CheckConstraint(
            "request_fingerprint IS NULL OR LENGTH(request_fingerprint) = 64",
            name="ck_payment_checkout_dispatch_fingerprint",
        ),
        sa.CheckConstraint(
            "(request_key IS NULL AND request_fingerprint IS NULL) OR "
            "(request_key IS NOT NULL AND request_fingerprint IS NOT NULL)",
            name="ck_payment_checkout_dispatch_request_pair",
        ),
        sa.CheckConstraint(
            "(publisher_token IS NULL AND publisher_lease_until IS NULL) OR "
            "(publisher_token IS NOT NULL AND publisher_lease_until IS NOT NULL)",
            name="ck_payment_checkout_dispatch_lease_pair",
        ),
        sa.CheckConstraint(
            "error_code IS NULL OR error_code IN "
            "('provider_unavailable', 'rate_limited', 'provider_rejected', "
            "'invalid_response', 'identity_collision', 'payload_corrupt', "
            "'config_invalid', 'purchase_terminal', 'binding_failed')",
            name="ck_payment_checkout_dispatch_error_code",
        ),
        sa.CheckConstraint(
            "(state = 'pending' AND provider_checkout_id IS NULL AND checkout_url IS NULL "
            "AND checkout_expires_at IS NULL AND ready_at IS NULL AND failed_at IS NULL "
            "AND next_attempt_at IS NOT NULL) OR "
            "(state = 'ready' AND provider_checkout_id IS NOT NULL AND checkout_url IS NOT NULL "
            "AND ready_at IS NOT NULL AND failed_at IS NULL AND next_attempt_at IS NULL "
            "AND publisher_token IS NULL AND publisher_lease_until IS NULL "
            "AND error_code IS NULL AND error_detail IS NULL) OR "
            "(state IN ('failed', 'cancelled') AND provider_checkout_id IS NULL AND checkout_url IS NULL "
            "AND checkout_expires_at IS NULL AND ready_at IS NULL AND failed_at IS NOT NULL "
            "AND next_attempt_at IS NULL AND publisher_token IS NULL "
            "AND publisher_lease_until IS NULL AND error_code IS NOT NULL)",
            name="ck_payment_checkout_dispatch_terminal_fields",
        ),
    )
    op.create_index(
        "ix_payment_checkout_dispatches_user_id",
        "payment_checkout_dispatches",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_payment_checkout_dispatch_due",
        "payment_checkout_dispatches",
        ["next_attempt_at", "created_at"],
        unique=False,
        postgresql_where=sa.text("state = 'pending'"),
        sqlite_where=sa.text("state = 'pending'"),
    )
    op.create_index(
        "uq_payment_checkout_dispatch_provider_checkout",
        "payment_checkout_dispatches",
        ["provider", "provider_checkout_id"],
        unique=True,
        postgresql_where=sa.text("provider_checkout_id IS NOT NULL"),
        sqlite_where=sa.text("provider_checkout_id IS NOT NULL"),
    )


def downgrade() -> None:
    connection = op.get_bind()
    pending = connection.execute(
        sa.text("SELECT COUNT(*) FROM payment_checkout_dispatches WHERE state = 'pending'")
    ).scalar_one()
    if pending:
        raise RuntimeError("pending payment checkout dispatches prevent downgrade")
    op.drop_index(
        "uq_payment_checkout_dispatch_provider_checkout",
        table_name="payment_checkout_dispatches",
    )
    op.drop_index("ix_payment_checkout_dispatch_due", table_name="payment_checkout_dispatches")
    op.drop_index("ix_payment_checkout_dispatches_user_id", table_name="payment_checkout_dispatches")
    op.drop_table("payment_checkout_dispatches")
