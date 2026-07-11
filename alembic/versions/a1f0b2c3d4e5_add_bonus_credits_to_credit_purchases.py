"""add bonus_credits to credit_purchases

Revision ID: a1f0b2c3d4e5
Revises: e7f1a2b3c4d5
Create Date: 2026-07-04 21:30:00.000000

Snapshot do bonus promocional (PURCHASE_BONUS_PERCENT) creditado junto com a compra,
para que estorno reverta base+bonus mesmo depois que a promocao acabar.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "a1f0b2c3d4e5"
down_revision: Union[str, None] = "e7f1a2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "credit_purchases",
        sa.Column("bonus_credits", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("credit_purchases", "bonus_credits")
