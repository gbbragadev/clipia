"""add append-only first-party analytics events

Revision ID: f3a4b5c6d7e8
Revises: e1f2a3b4c5d6
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f3a4b5c6d7e8"
down_revision: str | None = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_EVENT_NAMES = (
    "landing_viewed",
    "hero_cta_clicked",
    "example_played",
    "example_completed",
    "pricing_viewed",
    "pricing_package_selected",
    "support_opened",
    "signup_started",
    "credits_viewed",
    "credits_low",
    "user_returned",
    "referral_shared",
    "feedback_submitted",
)


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    properties_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
    op.create_table(
        "analytics_events",
        sa.Column("event_id", sa.UUID(), primary_key=True),
        sa.Column("event_name", sa.String(length=50), nullable=False),
        sa.Column("schema_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("authority", sa.String(length=10), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("anonymous_session_id", sa.UUID(), nullable=True),
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("page", sa.String(length=30), nullable=False),
        sa.Column("acquisition_source", sa.String(length=20), nullable=False),
        sa.Column("utm_source", sa.String(length=100), nullable=True),
        sa.Column("utm_medium", sa.String(length=100), nullable=True),
        sa.Column("utm_campaign", sa.String(length=100), nullable=True),
        sa.Column("utm_content", sa.String(length=100), nullable=True),
        sa.Column("utm_term", sa.String(length=100), nullable=True),
        sa.Column("device_class", sa.String(length=10), nullable=False),
        sa.Column("properties", properties_type, nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.CheckConstraint(f"event_name IN ({_quoted(_EVENT_NAMES)})", name="ck_analytics_event_name"),
        sa.CheckConstraint("schema_version = 1", name="ck_analytics_schema_version"),
        sa.CheckConstraint("authority IN ('client', 'server')", name="ck_analytics_authority"),
        sa.CheckConstraint(
            "page IN ('landing', 'examples', 'niche', 'blog', 'support', 'auth_register', "
            "'credits', 'dashboard', 'editor', 'viewer')",
            name="ck_analytics_page",
        ),
        sa.CheckConstraint(
            "acquisition_source IN ('direct', 'organic', 'referral', 'social', 'email', 'paid', 'campaign')",
            name="ck_analytics_acquisition_source",
        ),
        sa.CheckConstraint(
            "device_class IN ('desktop', 'mobile', 'tablet', 'unknown')",
            name="ck_analytics_device_class",
        ),
        sa.CheckConstraint("LENGTH(payload_hash) = 64", name="ck_analytics_payload_hash"),
    )
    op.create_index("ix_analytics_events_event_time", "analytics_events", ["event_name", "occurred_at"])
    op.create_index(
        "ix_analytics_events_session_time",
        "analytics_events",
        ["anonymous_session_id", "occurred_at"],
    )
    op.create_index(
        "ix_analytics_events_user_time",
        "analytics_events",
        ["user_id", "occurred_at"],
        postgresql_where=sa.text("user_id IS NOT NULL"),
        sqlite_where=sa.text("user_id IS NOT NULL"),
    )
    op.create_index(
        "ix_analytics_events_event_user_time",
        "analytics_events",
        ["event_name", "user_id", "occurred_at"],
    )

    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(
            """
            CREATE FUNCTION clipia_reject_analytics_events_mutation()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION 'analytics_events is append-only';
            END;
            $$
            """
        )
        op.execute(
            """
            CREATE TRIGGER analytics_events_append_only
            BEFORE UPDATE OR DELETE ON analytics_events
            FOR EACH ROW EXECUTE FUNCTION clipia_reject_analytics_events_mutation()
            """
        )
    elif dialect == "sqlite":
        op.execute(
            """
            CREATE TRIGGER analytics_events_append_only_update
            BEFORE UPDATE ON analytics_events
            BEGIN SELECT RAISE(ABORT, 'analytics_events is append-only'); END
            """
        )
        op.execute(
            """
            CREATE TRIGGER analytics_events_append_only_delete
            BEFORE DELETE ON analytics_events
            BEGIN SELECT RAISE(ABORT, 'analytics_events is append-only'); END
            """
        )


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS analytics_events_append_only ON analytics_events")
        op.execute("DROP FUNCTION IF EXISTS clipia_reject_analytics_events_mutation()")
    elif dialect == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS analytics_events_append_only_update")
        op.execute("DROP TRIGGER IF EXISTS analytics_events_append_only_delete")

    op.drop_index("ix_analytics_events_event_user_time", table_name="analytics_events")
    op.drop_index("ix_analytics_events_user_time", table_name="analytics_events")
    op.drop_index("ix_analytics_events_session_time", table_name="analytics_events")
    op.drop_index("ix_analytics_events_event_time", table_name="analytics_events")
    op.drop_table("analytics_events")
