"""add processed payment events

Revision ID: d4e5f6a7b8c9
Revises: b7c8d9e0f1a2
Create Date: 2026-07-12
"""

import sqlalchemy as sa

from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "processed_payment_events",
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("event_key", sa.String(length=255), nullable=False),
        sa.Column("purchase_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["purchase_id"], ["credit_purchases.id"]),
        sa.PrimaryKeyConstraint("provider", "event_key"),
    )
    op.create_index(
        op.f("ix_processed_payment_events_purchase_id"),
        "processed_payment_events",
        ["purchase_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_processed_payment_events_purchase_id"), table_name="processed_payment_events")
    op.drop_table("processed_payment_events")
