"""add durable generation and rerender operation state

Revision ID: f6e7d8c9b0a1
Revises: d4e5f6a7b8c9
Create Date: 2026-07-12
"""

import sqlalchemy as sa
from alembic import op

revision: str = "f6e7d8c9b0a1"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("generation_dispatched_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("generation_refunded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("rerender_operation_id", sa.UUID(), nullable=True))
    op.add_column(
        "jobs",
        sa.Column("rerender_state", sa.String(length=20), server_default=sa.text("'idle'"), nullable=False),
    )
    op.add_column(
        "jobs",
        sa.Column("rerender_cost", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "jobs",
        sa.Column("rerender_pending_credits", sa.Float(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column("jobs", sa.Column("rerender_debited_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("rerender_dispatched_at", sa.DateTime(timezone=True), nullable=True))

    op.execute(sa.text("UPDATE jobs SET generation_dispatched_at = created_at WHERE generation_dispatched_at IS NULL"))
    op.create_index(
        "ix_jobs_rerender_state_debited_at",
        "jobs",
        ["rerender_state", "rerender_debited_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_jobs_rerender_state_debited_at", table_name="jobs")
    op.drop_column("jobs", "rerender_dispatched_at")
    op.drop_column("jobs", "rerender_debited_at")
    op.drop_column("jobs", "rerender_pending_credits")
    op.drop_column("jobs", "rerender_cost")
    op.drop_column("jobs", "rerender_state")
    op.drop_column("jobs", "rerender_operation_id")
    op.drop_column("jobs", "cancel_requested_at")
    op.drop_column("jobs", "generation_refunded_at")
    op.drop_column("jobs", "generation_dispatched_at")
