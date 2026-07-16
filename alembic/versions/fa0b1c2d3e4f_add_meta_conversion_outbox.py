"""add consent-gated Meta conversion outbox

Revision ID: fa0b1c2d3e4f
Revises: f9a0b1c2d3e4
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "fa0b1c2d3e4f"
down_revision: str | None = "f9a0b1c2d3e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    payload_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
    op.create_table(
        "meta_conversion_outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.String(length=100), nullable=False),
        sa.Column("event_name", sa.String(length=50), nullable=False),
        sa.Column("payload", payload_type, nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("attempts >= 0", name="ck_meta_outbox_attempts_nonnegative"),
        sa.CheckConstraint(
            "status IN ('pending', 'retry', 'sent', 'failed', 'cancelled')",
            name="ck_meta_outbox_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_meta_conversion_outbox_event_id"),
    )
    op.create_index(
        "ix_meta_outbox_dispatch",
        "meta_conversion_outbox",
        ["status", "next_attempt_at"],
        unique=False,
    )
    op.create_index(
        "ix_meta_outbox_user_status",
        "meta_conversion_outbox",
        ["user_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_meta_outbox_user_status", table_name="meta_conversion_outbox")
    op.drop_index("ix_meta_outbox_dispatch", table_name="meta_conversion_outbox")
    op.drop_table("meta_conversion_outbox")
