"""add opt-in public video shares and qualified visits

Revision ID: f9a0b1c2d3e4
Revises: e8f9a0b1c2d3
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f9a0b1c2d3e4"
down_revision: str | None = "e8f9a0b1c2d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ANALYTICS_EVENTS_BEFORE = (
    "event_name IN ('landing_viewed', 'hero_cta_clicked', 'example_played', "
    "'example_completed', 'pricing_viewed', 'pricing_package_selected', "
    "'support_opened', 'signup_started', 'credits_viewed', 'credits_low', "
    "'user_returned', 'referral_shared', 'feedback_submitted', "
    "'onboarding_step_viewed', 'editor_opened', 'user_registered', "
    "'email_verified', 'generation_requested', 'generation_completed', "
    "'generation_failed', 'video_exported', 'checkout_started', "
    "'payment_completed', 'credit_balance_changed', 'second_generation_requested')"
)
_ANALYTICS_EVENTS_AFTER = _ANALYTICS_EVENTS_BEFORE[:-1] + (
    ", 'share_page_published', 'share_page_visited', 'social_share_rewarded')"
)
_SQLITE_UUID = (
    "lower(hex(randomblob(4))) || '-' || lower(hex(randomblob(2))) || '-' || "
    "lower(hex(randomblob(2))) || '-' || lower(hex(randomblob(2))) || '-' || "
    "lower(hex(randomblob(6)))"
)


def _replace_analytics_event_constraint(expression: str) -> None:
    with op.batch_alter_table("analytics_events") as batch_op:
        batch_op.drop_constraint("ck_analytics_event_name", type_="check")
        batch_op.create_check_constraint("ck_analytics_event_name", expression)


def _replace_sqlite_ledger_update_trigger(*, contextual: bool) -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite" or "credit_ledger_entries" not in sa.inspect(bind).get_table_names():
        return
    op.execute("DROP TRIGGER IF EXISTS credit_ledger_users_update")
    if contextual:
        op.execute(
            f"""
            CREATE TRIGGER credit_ledger_users_update
            AFTER UPDATE OF credits ON users
            WHEN NEW.credits <> OLD.credits
            BEGIN
                INSERT INTO credit_ledger_entries (
                    id, user_id, delta, origin, purchase_id, job_id, operation_id,
                    reason, idempotency_key, balance_after, created_at
                ) VALUES (
                    {_SQLITE_UUID}, NEW.id, NEW.credits - OLD.credits,
                    COALESCE(clipia_get_credit_context('origin'), 'unclassified'),
                    clipia_get_credit_context('purchase_id'),
                    clipia_get_credit_context('job_id'),
                    clipia_get_credit_context('operation_id'),
                    COALESCE(clipia_get_credit_context('reason'), 'unclassified projection mutation'),
                    COALESCE(
                        clipia_get_credit_context('idempotency_key'),
                        'shadow:' || lower(hex(randomblob(16)))
                    ),
                    NEW.credits, CURRENT_TIMESTAMP
                );
                SELECT clipia_clear_credit_context();
            END
            """
        )
    else:
        op.execute(
            f"""
            CREATE TRIGGER credit_ledger_users_update
            AFTER UPDATE OF credits ON users
            WHEN NEW.credits <> OLD.credits
            BEGIN
                INSERT INTO credit_ledger_entries (
                    id, user_id, delta, origin, reason, idempotency_key,
                    balance_after, created_at
                ) VALUES (
                    {_SQLITE_UUID}, NEW.id, NEW.credits - OLD.credits,
                    'unclassified', 'unclassified projection mutation',
                    'shadow:' || lower(hex(randomblob(16))), NEW.credits, CURRENT_TIMESTAMP
                );
            END
            """
        )


def upgrade() -> None:
    op.create_table(
        "public_video_shares",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(active = true AND revoked_at IS NULL) OR (active = false AND revoked_at IS NOT NULL)",
            name="ck_public_video_share_revocation_state",
        ),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_public_video_shares_token_hash"),
    )
    op.create_index(
        "uq_public_video_shares_active_job",
        "public_video_shares",
        ["job_id"],
        unique=True,
        postgresql_where=sa.text("active = true"),
        sqlite_where=sa.text("active = 1"),
    )
    op.create_index(
        "ix_public_video_shares_owner_created",
        "public_video_shares",
        ["owner_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "public_share_visits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("share_id", sa.Uuid(), nullable=False),
        sa.Column("anonymous_session_id", sa.Uuid(), nullable=False),
        sa.Column("user_agent_classification", sa.String(length=20), nullable=False),
        sa.Column("visited_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "user_agent_classification IN ('browser', 'bot', 'unknown')",
            name="ck_public_share_visit_user_agent_classification",
        ),
        sa.ForeignKeyConstraint(["share_id"], ["public_video_shares.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "share_id",
            "anonymous_session_id",
            name="uq_public_share_visit_session",
        ),
    )
    op.create_index(
        "ix_public_share_visits_share_visited",
        "public_share_visits",
        ["share_id", "visited_at"],
        unique=False,
    )
    _replace_analytics_event_constraint(_ANALYTICS_EVENTS_AFTER)
    _replace_sqlite_ledger_update_trigger(contextual=True)


def downgrade() -> None:
    _replace_sqlite_ledger_update_trigger(contextual=False)
    _replace_analytics_event_constraint(_ANALYTICS_EVENTS_BEFORE)
    op.drop_index("ix_public_share_visits_share_visited", table_name="public_share_visits")
    op.drop_table("public_share_visits")
    op.drop_index("ix_public_video_shares_owner_created", table_name="public_video_shares")
    op.drop_index("uq_public_video_shares_active_job", table_name="public_video_shares")
    op.drop_table("public_video_shares")
