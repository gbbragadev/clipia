"""add jobs.user_id index

Revision ID: f2b6c6a9d51b
Revises: b5c55cc9bcac
Create Date: 2026-04-04 22:10:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "f2b6c6a9d51b"
down_revision: Union[str, None] = "b5c55cc9bcac"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_jobs_user_id", "jobs", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_jobs_user_id", table_name="jobs")
