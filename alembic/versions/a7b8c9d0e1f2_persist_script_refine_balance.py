"""persist script refine balance

Revision ID: a7b8c9d0e1f2
Revises: f6e7d8c9b0a1
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "f6e7d8c9b0a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("script_refine_pending", sa.Float(), server_default="0", nullable=False),
    )
    op.add_column(
        "users",
        sa.Column("script_refine_redis_migrated", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "jobs",
        sa.Column("refine_credit_cost", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("jobs", "refine_credit_cost")
    op.drop_column("users", "script_refine_redis_migrated")
    op.drop_column("users", "script_refine_pending")
