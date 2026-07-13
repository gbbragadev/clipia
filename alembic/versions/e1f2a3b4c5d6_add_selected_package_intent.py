"""add nullable public package intent

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: str | None = "d0e1f2a3b4c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("selected_package", sa.String(length=20), nullable=True))
        batch_op.create_check_constraint(
            "ck_users_selected_package",
            "selected_package IS NULL OR selected_package IN ('starter', 'popular', 'professional')",
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("ck_users_selected_package", type_="check")
        batch_op.drop_column("selected_package")
