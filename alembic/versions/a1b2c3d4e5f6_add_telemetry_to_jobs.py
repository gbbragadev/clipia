"""add telemetry jsonb to jobs

Revision ID: a1b2c3d4e5f6
Revises: c3d2e1f0a9b8
Create Date: 2026-07-10 21:00:00.000000

Telemetria de economia por job (dono pediu: "senão estou gerando vídeo e perdendo
dinheiro"): duração por etapa da pipeline + custo estimado de API em USD, consolidados
no finalize. Alimenta a aba Economia do admin e os gatilhos do docs/PLANO-ESCALA.md.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "c3d2e1f0a9b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("telemetry", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "telemetry")
