"""add campaign offers and activated acquisition rewards

Revision ID: e8f9a0b1c2d3
Revises: d7e8f9a0b1c2
Create Date: 2026-07-16
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e8f9a0b1c2d3"
down_revision: str | None = "d7e8f9a0b1c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OFFER_NAMESPACE = uuid.UUID("ad26227c-fd76-430f-a834-64cdd3a8d86e")


def upgrade() -> None:
    op.create_table(
        "marketing_offers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("bonus_credits", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("bonus_credits > 0", name="ck_marketing_offer_bonus_positive"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_marketing_offers_code"),
    )
    op.create_index("ix_marketing_offers_active_code", "marketing_offers", ["is_active", "code"], unique=False)
    offers = sa.table(
        "marketing_offers",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("bonus_credits", sa.Integer()),
        sa.column("is_active", sa.Boolean()),
        sa.column("expires_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        offers,
        [
            {
                "id": uuid.uuid5(_OFFER_NAMESPACE, "creator20_v1"),
                "code": "creator20_v1",
                "bonus_credits": 18,
                "is_active": True,
                "expires_at": None,
            }
        ],
    )

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("acquisition_offer_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("marketing_measurement_consented_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_foreign_key(
            "fk_users_acquisition_offer_id_marketing_offers",
            "marketing_offers",
            ["acquisition_offer_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    op.create_table(
        "acquisition_rewards",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("reward_type", sa.String(length=30), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("marketing_offer_id", sa.Uuid(), nullable=True),
        sa.Column("source_user_id", sa.Uuid(), nullable=True),
        sa.Column("completed_job_id", sa.Uuid(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("credits > 0", name="ck_acquisition_reward_credits_positive"),
        sa.CheckConstraint(
            "reward_type IN ('campaign_signup', 'referral_activation', 'social_share')",
            name="ck_acquisition_reward_type",
        ),
        sa.ForeignKeyConstraint(["completed_job_id"], ["jobs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["marketing_offer_id"], ["marketing_offers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "reward_type", name="uq_acquisition_reward_user_type"),
    )
    op.create_index(
        "uq_acquisition_reward_user_acquisition",
        "acquisition_rewards",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("reward_type IN ('campaign_signup', 'referral_activation')"),
        sqlite_where=sa.text("reward_type IN ('campaign_signup', 'referral_activation')"),
    )
    op.create_index(
        "ix_acquisition_rewards_type_occurred",
        "acquisition_rewards",
        ["reward_type", "occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_acquisition_rewards_type_occurred", table_name="acquisition_rewards")
    op.drop_index("uq_acquisition_reward_user_acquisition", table_name="acquisition_rewards")
    op.drop_table("acquisition_rewards")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("fk_users_acquisition_offer_id_marketing_offers", type_="foreignkey")
        batch_op.drop_column("marketing_measurement_consented_at")
        batch_op.drop_column("acquisition_offer_id")
    op.drop_index("ix_marketing_offers_active_code", table_name="marketing_offers")
    op.drop_table("marketing_offers")
