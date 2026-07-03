"""add lgpd consent fields to users

Revision ID: e7f1a2b3c4d5
Revises: c1a2b3d4e5f6
Create Date: 2026-07-02 12:00:00.000000

Adiciona colunas de comprovante de consentimento LGPD (consented_at, consent_ip)
para auditoria do aceite expresso dos Termos de Uso e Política de Privacidade no cadastro.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "e7f1a2b3c4d5"
down_revision: Union[str, None] = "c1a2b3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("consent_ip", sa.String(length=45), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "consent_ip")
    op.drop_column("users", "consented_at")
