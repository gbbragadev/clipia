"""add one-time password reset tokens and legal consent versions

Revision ID: a4b5c6d7e8f9
Revises: f3a4b5c6d7e8
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a4b5c6d7e8f9"
down_revision: str | None = "f3a4b5c6d7e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("consent_terms_version", sa.String(length=20), nullable=True))
    op.add_column("users", sa.Column("consent_privacy_version", sa.String(length=20), nullable=True))
    op.create_table(
        "password_reset_tokens",
        sa.Column("jti", sa.UUID(), primary_key=True),
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("expires_at > issued_at", name="ck_password_reset_token_expiry"),
    )
    op.create_index(
        "ix_password_reset_tokens_user_used",
        "password_reset_tokens",
        ["user_id", "used_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_password_reset_tokens_user_used", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_column("users", "consent_privacy_version")
    op.drop_column("users", "consent_terms_version")
