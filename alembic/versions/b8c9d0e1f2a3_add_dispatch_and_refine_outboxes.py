"""add dispatch and refine projection outboxes

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: str | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("script_refine_version", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_table(
        "job_dispatches",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("job_id", sa.UUID(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("operation_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("debited_credits", sa.Integer(), server_default="0", nullable=False),
        sa.Column("refine_debited", sa.Float(), server_default="0", nullable=False),
        sa.Column("pending_credits_snapshot", sa.Float(), server_default="0", nullable=False),
        sa.Column("state", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_task_id", sa.UUID(), nullable=True),
        sa.Column("publisher_token", sa.UUID(), nullable=True),
        sa.Column("publisher_lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_task_id", sa.UUID(), nullable=True),
        sa.Column("worker_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("kind", "operation_id", name="uq_job_dispatch_kind_operation"),
        sa.CheckConstraint("kind IN ('generation', 'rerender')", name="ck_job_dispatch_kind"),
        sa.CheckConstraint("debited_credits >= 0", name="ck_job_dispatch_debited_credits"),
        sa.CheckConstraint("refine_debited >= 0", name="ck_job_dispatch_refine_debited"),
        sa.CheckConstraint("pending_credits_snapshot >= 0", name="ck_job_dispatch_pending_snapshot"),
        sa.CheckConstraint(
            "state IN ('pending', 'published', 'claimed', 'completed', 'cancelled')",
            name="ck_job_dispatch_state",
        ),
    )
    op.create_index("ix_job_dispatches_job_id", "job_dispatches", ["job_id"], unique=False)
    op.create_index(
        "ix_job_dispatch_state_attempt",
        "job_dispatches",
        ["state", "last_attempt_at"],
        unique=False,
    )
    op.create_table(
        "refine_balance_outbox",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.UniqueConstraint("user_id", "version", name="uq_refine_balance_outbox_user_version"),
    )
    op.create_index("ix_refine_balance_outbox_user_id", "refine_balance_outbox", ["user_id"], unique=False)
    op.create_index(
        "ix_refine_balance_outbox_applied",
        "refine_balance_outbox",
        ["applied_at", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    connection = op.get_bind()
    pending_refine = connection.execute(
        sa.text("SELECT COUNT(*) FROM refine_balance_outbox WHERE applied_at IS NULL")
    ).scalar_one()
    if pending_refine:
        raise RuntimeError(
            "refine balance projections are pending; drain_refine_balance_outbox must finish before downgrade"
        )
    unhanded_refine = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM users "
            "WHERE script_refine_redis_migrated IS TRUE "
            "OR ABS(COALESCE(script_refine_pending, 0)) > 0.000001"
        )
    ).scalar_one()
    if unhanded_refine:
        raise RuntimeError(
            "refine balance authority has not been handed off; "
            "run python -m scripts.pre_rollback_refine_gate before downgrade"
        )
    active_dispatches = connection.execute(
        sa.text("SELECT COUNT(*) FROM job_dispatches WHERE state IN ('pending', 'published', 'claimed')")
    ).scalar_one()
    if active_dispatches:
        raise RuntimeError("active job dispatches prevent downgrade; drain or terminalize the dispatch outbox first")

    op.drop_table("refine_balance_outbox")
    op.drop_table("job_dispatches")
    op.drop_column("users", "script_refine_version")
