"""expand first-party analytics event catalog

Revision ID: c6d7e8f9a0b1
Revises: b5c6d7e8f9a0
Create Date: 2026-07-13
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c6d7e8f9a0b1"
down_revision: str | None = "b5c6d7e8f9a0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CLIENT_EVENT_NAMES = (
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
_EXPANDED_EVENT_NAMES = _CLIENT_EVENT_NAMES + (
    "onboarding_step_viewed",
    "editor_opened",
    "user_registered",
    "email_verified",
    "generation_requested",
    "generation_completed",
    "generation_failed",
    "video_exported",
    "checkout_started",
    "payment_completed",
    "credit_balance_changed",
    "second_generation_requested",
)


def _constraint(names: tuple[str, ...]) -> str:
    return "event_name IN (" + ", ".join(f"'{name}'" for name in names) + ")"


def _drop_sqlite_append_only_triggers() -> None:
    op.execute("DROP TRIGGER IF EXISTS analytics_events_append_only_update")
    op.execute("DROP TRIGGER IF EXISTS analytics_events_append_only_delete")


def _create_sqlite_append_only_triggers() -> None:
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


def _replace_constraint(names: tuple[str, ...]) -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        _drop_sqlite_append_only_triggers()
        with op.batch_alter_table("analytics_events", recreate="always") as batch_op:
            batch_op.drop_constraint("ck_analytics_event_name", type_="check")
            batch_op.create_check_constraint("ck_analytics_event_name", _constraint(names))
        _create_sqlite_append_only_triggers()
        return

    op.drop_constraint("ck_analytics_event_name", "analytics_events", type_="check")
    op.create_check_constraint("ck_analytics_event_name", "analytics_events", _constraint(names))


def upgrade() -> None:
    _replace_constraint(_EXPANDED_EVENT_NAMES)


def downgrade() -> None:
    _replace_constraint(_CLIENT_EVENT_NAMES)
