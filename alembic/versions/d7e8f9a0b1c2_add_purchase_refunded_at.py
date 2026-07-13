"""add refund timestamp, resumable rerender claim, and durable referral awards

Revision ID: d7e8f9a0b1c2
Revises: c6d7e8f9a0b1
Create Date: 2026-07-13
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d7e8f9a0b1c2"
down_revision: str | None = "c6d7e8f9a0b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LEGACY_REFERRAL_NAMESPACE = uuid.UUID("ca7735cf-b932-4acf-a541-c6138813238d")
_MAX_REFERRAL_AWARDS = 10


def _uuid_value(value) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _backfill_legacy_referral_awards() -> None:
    """Freeze up to ten legacy verified referrals per referrer.

    Ledger evidence is authoritative when available. Older installations without
    classified ledger rows fall back to the first ten verified referrals by
    registration time, matching the legacy count-based award rule conservatively.
    """
    bind = op.get_bind()
    candidate_rows = list(
        bind.execute(
            sa.text(
                "SELECT id, referred_by FROM users "
                "WHERE referred_by IS NOT NULL AND email_verified IS TRUE "
                "ORDER BY created_at ASC, id ASC"
            )
        ).mappings()
    )
    candidates = {
        str(_uuid_value(row["id"])): (_uuid_value(row["id"]), _uuid_value(row["referred_by"])) for row in candidate_rows
    }
    selected: list[tuple[uuid.UUID, uuid.UUID]] = []
    selected_ids: set[uuid.UUID] = set()
    counts: dict[uuid.UUID, int] = {}

    if "credit_ledger_entries" in sa.inspect(bind).get_table_names():
        ledger_rows = bind.execute(
            sa.text(
                "SELECT user_id, idempotency_key FROM credit_ledger_entries "
                "WHERE origin = 'referral_bonus' AND idempotency_key LIKE 'referral:%' "
                "ORDER BY created_at ASC, id ASC"
            )
        ).mappings()
        for row in ledger_rows:
            key = str(row["idempotency_key"])
            referred_key = key.removeprefix("referral:")
            if ":" in referred_key:
                continue
            candidate = candidates.get(referred_key)
            if candidate is None:
                continue
            referred_id, referrer_id = candidate
            if referrer_id != _uuid_value(row["user_id"]):
                continue
            if referred_id in selected_ids or counts.get(referrer_id, 0) >= _MAX_REFERRAL_AWARDS:
                continue
            selected.append(candidate)
            selected_ids.add(referred_id)
            counts[referrer_id] = counts.get(referrer_id, 0) + 1

    for referred_id, referrer_id in candidates.values():
        if referred_id in selected_ids or counts.get(referrer_id, 0) >= _MAX_REFERRAL_AWARDS:
            continue
        selected.append((referred_id, referrer_id))
        selected_ids.add(referred_id)
        counts[referrer_id] = counts.get(referrer_id, 0) + 1

    if not selected:
        return
    awards = sa.table(
        "referral_credit_awards",
        sa.column("id", sa.Uuid()),
        sa.column("referred_user_id", sa.Uuid()),
        sa.column("referrer_user_id", sa.Uuid()),
        sa.column("credits", sa.Integer()),
    )
    bind.execute(
        sa.insert(awards),
        [
            {
                "id": uuid.uuid5(_LEGACY_REFERRAL_NAMESPACE, f"legacy-referral:{referred_id}"),
                "referred_user_id": referred_id,
                "referrer_user_id": referrer_id,
                "credits": 2,
            }
            for referred_id, referrer_id in selected
        ],
    )


def upgrade() -> None:
    op.add_column("credit_purchases", sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        "UPDATE credit_purchases SET refunded_at = COALESCE(paid_at, created_at) "
        "WHERE payment_state = 'refunded' OR LOWER(status) IN ('refunded', 'charged_back')"
    )
    op.create_index("ix_credit_purchases_refunded_at", "credit_purchases", ["refunded_at"], unique=False)
    op.add_column("jobs", sa.Column("legacy_rerender_task_id", sa.String(length=255), nullable=True))
    op.create_table(
        "referral_credit_awards",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("referred_user_id", sa.Uuid(), nullable=False),
        sa.Column("referrer_user_id", sa.Uuid(), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("credits > 0", name="ck_referral_credit_award_credits_positive"),
        sa.ForeignKeyConstraint(["referred_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["referrer_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("referred_user_id", name="uq_referral_credit_award_referred_user"),
    )
    op.create_index(
        "ix_referral_credit_awards_referrer_created",
        "referral_credit_awards",
        ["referrer_user_id", "created_at"],
        unique=False,
    )
    _backfill_legacy_referral_awards()


def downgrade() -> None:
    op.drop_index("ix_referral_credit_awards_referrer_created", table_name="referral_credit_awards")
    op.drop_table("referral_credit_awards")
    op.drop_column("jobs", "legacy_rerender_task_id")
    op.drop_index("ix_credit_purchases_refunded_at", table_name="credit_purchases")
    op.drop_column("credit_purchases", "refunded_at")
