"""add provider to credit_purchases

Revision ID: c1a2b3d4e5f6
Revises: 1b254e9e8620
Create Date: 2026-06-30 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "c1a2b3d4e5f6"
down_revision: Union[str, None] = "1b254e9e8620"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Segundo provedor de pagamento (Stripe). server_default cobre as linhas existentes (MP).
    op.add_column(
        "credit_purchases",
        sa.Column("provider", sa.String(length=20), nullable=False, server_default="mercadopago"),
    )


def downgrade() -> None:
    op.drop_column("credit_purchases", "provider")
