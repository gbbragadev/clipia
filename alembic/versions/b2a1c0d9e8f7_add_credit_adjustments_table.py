"""add credit_adjustments table

Revision ID: b2a1c0d9e8f7
Revises: a1f0b2c3d4e5
Create Date: 2026-07-04 21:40:00.000000

Auditoria de ajustes manuais de creditos feitos pelo admin no painel
(quem ajustou, quanto, saldo antes/depois e motivo obrigatorio).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from alembic import op

revision: str = "b2a1c0d9e8f7"
down_revision: Union[str, None] = "a1f0b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "credit_adjustments",
        sa.Column("id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("admin_user_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("target_user_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("previous_balance", sa.Integer(), nullable=False),
        sa.Column("new_balance", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["admin_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_credit_adjustments_target_user_id"), "credit_adjustments", ["target_user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_credit_adjustments_target_user_id"), table_name="credit_adjustments")
    op.drop_table("credit_adjustments")
