"""add missing indexes for jobs and credit_purchases

Revision ID: e3e606f12b81
Revises: f2b6c6a9d51b
Create Date: 2026-04-05 17:17:04.334758
"""

from typing import Sequence, Union

from alembic import op

revision: str = "e3e606f12b81"
down_revision: Union[str, None] = "f2b6c6a9d51b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_created_at", "jobs", ["created_at"])
    op.create_index("ix_credit_purchases_user_id", "credit_purchases", ["user_id"])
    op.create_index("ix_credit_purchases_status", "credit_purchases", ["status"])


def downgrade() -> None:
    op.drop_index("ix_credit_purchases_status", table_name="credit_purchases")
    op.drop_index("ix_credit_purchases_user_id", table_name="credit_purchases")
    op.drop_index("ix_jobs_created_at", table_name="jobs")
    op.drop_index("ix_jobs_status", table_name="jobs")
