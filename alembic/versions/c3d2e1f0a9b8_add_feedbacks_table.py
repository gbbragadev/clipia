"""add feedbacks table

Revision ID: c3d2e1f0a9b8
Revises: b2a1c0d9e8f7
Create Date: 2026-07-04 21:50:00.000000

Feedback de usuarios do beta: widget in-app (nota 1-5 + comentario) e prompt
pos-video (por job), exibidos na aba Feedback do painel admin.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from alembic import op

revision: str = "c3d2e1f0a9b8"
down_revision: Union[str, None] = "b2a1c0d9e8f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "feedbacks",
        sa.Column("id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("job_id", PG_UUID(as_uuid=True), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_feedbacks_user_id"), "feedbacks", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_feedbacks_user_id"), table_name="feedbacks")
    op.drop_table("feedbacks")
