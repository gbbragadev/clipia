"""add append-only shadow credit ledger and reconciliation evidence

Revision ID: b5c6d7e8f9a0
Revises: a4b5c6d7e8f9
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b5c6d7e8f9a0"
down_revision: str | None = "a4b5c6d7e8f9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SQLITE_UUID = (
    "lower(hex(randomblob(4))) || '-' || lower(hex(randomblob(2))) || '-' || "
    "lower(hex(randomblob(2))) || '-' || lower(hex(randomblob(2))) || '-' || "
    "lower(hex(randomblob(6)))"
)


def _create_sqlite_triggers() -> None:
    op.execute(
        f"""
        CREATE TRIGGER credit_ledger_users_insert
        AFTER INSERT ON users
        WHEN NEW.credits <> 0
        BEGIN
            INSERT INTO credit_ledger_entries (
                id, user_id, delta, origin, reason, idempotency_key,
                balance_after, created_at
            ) VALUES (
                {_SQLITE_UUID}, NEW.id, NEW.credits, 'user_insert',
                'initial nonzero balance',
                'shadow:' || lower(hex(randomblob(16))), NEW.credits, CURRENT_TIMESTAMP
            );
        END
        """
    )
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
    op.execute(
        """
        CREATE TRIGGER credit_ledger_entries_no_update
        BEFORE UPDATE ON credit_ledger_entries
        BEGIN SELECT RAISE(ABORT, 'credit_ledger_entries is append-only'); END
        """
    )
    op.execute(
        """
        CREATE TRIGGER credit_ledger_entries_no_delete
        BEFORE DELETE ON credit_ledger_entries
        BEGIN SELECT RAISE(ABORT, 'credit_ledger_entries is append-only'); END
        """
    )


def _create_postgres_triggers() -> None:
    op.execute(
        """
        CREATE FUNCTION clipia_reject_credit_ledger_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'credit_ledger_entries is append-only';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER credit_ledger_entries_append_only
        BEFORE UPDATE OR DELETE ON credit_ledger_entries
        FOR EACH ROW EXECUTE FUNCTION clipia_reject_credit_ledger_mutation()
        """
    )
    op.execute(
        """
        CREATE FUNCTION clipia_record_credit_projection_change()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            v_delta integer;
            v_origin text;
            v_reason text;
            v_idempotency_key text;
            v_purchase_id uuid;
            v_job_id uuid;
            v_operation_id uuid;
            v_mode text;
        BEGIN
            IF TG_OP = 'INSERT' THEN
                v_delta := NEW.credits;
            ELSE
                v_delta := NEW.credits - OLD.credits;
            END IF;

            IF v_delta = 0 THEN
                RETURN NEW;
            END IF;

            v_origin := COALESCE(
                NULLIF(current_setting('clipia.credit_origin', true), ''),
                CASE WHEN TG_OP = 'INSERT' THEN 'user_insert' ELSE 'unclassified' END
            );
            v_reason := COALESCE(
                NULLIF(current_setting('clipia.credit_reason', true), ''),
                CASE WHEN TG_OP = 'INSERT' THEN 'initial nonzero balance'
                     ELSE 'unclassified projection mutation' END
            );
            v_idempotency_key := COALESCE(
                NULLIF(current_setting('clipia.credit_idempotency_key', true), ''),
                'shadow:' || md5(random()::text || clock_timestamp()::text)
            );
            v_purchase_id := NULLIF(current_setting('clipia.credit_purchase_id', true), '')::uuid;
            v_job_id := NULLIF(current_setting('clipia.credit_job_id', true), '')::uuid;
            v_operation_id := NULLIF(current_setting('clipia.credit_operation_id', true), '')::uuid;
            v_mode := COALESCE(NULLIF(current_setting('clipia.credit_ledger_mode', true), ''), 'shadow');

            IF v_mode = 'enforce' THEN
                INSERT INTO credit_ledger_entries (
                    id, user_id, delta, origin, purchase_id, job_id, operation_id,
                    reason, idempotency_key, balance_after, created_at
                ) VALUES (
                    md5(random()::text || clock_timestamp()::text)::uuid,
                    NEW.id, v_delta, v_origin, v_purchase_id, v_job_id, v_operation_id,
                    v_reason, v_idempotency_key, NEW.credits, now()
                );
            ELSE
                INSERT INTO credit_ledger_entries (
                    id, user_id, delta, origin, purchase_id, job_id, operation_id,
                    reason, idempotency_key, balance_after, created_at
                ) VALUES (
                    md5(random()::text || clock_timestamp()::text)::uuid,
                    NEW.id, v_delta, v_origin, v_purchase_id, v_job_id, v_operation_id,
                    v_reason, v_idempotency_key, NEW.credits, now()
                ) ON CONFLICT (idempotency_key) DO NOTHING;
            END IF;

            PERFORM set_config('clipia.credit_origin', '', true);
            PERFORM set_config('clipia.credit_reason', '', true);
            PERFORM set_config('clipia.credit_idempotency_key', '', true);
            PERFORM set_config('clipia.credit_purchase_id', '', true);
            PERFORM set_config('clipia.credit_job_id', '', true);
            PERFORM set_config('clipia.credit_operation_id', '', true);
            PERFORM set_config('clipia.credit_ledger_mode', '', true);
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER credit_ledger_users_insert
        AFTER INSERT ON users
        FOR EACH ROW EXECUTE FUNCTION clipia_record_credit_projection_change()
        """
    )
    op.execute(
        """
        CREATE TRIGGER credit_ledger_users_update
        AFTER UPDATE OF credits ON users
        FOR EACH ROW EXECUTE FUNCTION clipia_record_credit_projection_change()
        """
    )


def upgrade() -> None:
    details_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
    op.create_table(
        "credit_ledger_entries",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("origin", sa.String(length=50), nullable=False),
        sa.Column("purchase_id", sa.UUID(), nullable=True),
        sa.Column("job_id", sa.UUID(), nullable=True),
        sa.Column("operation_id", sa.UUID(), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("delta <> 0", name="ck_credit_ledger_delta_nonzero"),
        sa.CheckConstraint("balance_after >= 0", name="ck_credit_ledger_balance_nonnegative"),
        sa.UniqueConstraint("idempotency_key", name="uq_credit_ledger_idempotency_key"),
    )
    op.create_index("ix_credit_ledger_user_created", "credit_ledger_entries", ["user_id", "created_at"])
    op.create_index("ix_credit_ledger_origin_created", "credit_ledger_entries", ["origin", "created_at"])
    op.create_table(
        "credit_ledger_reconciliation_runs",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("mode", sa.String(length=10), nullable=False),
        sa.Column("user_count", sa.Integer(), nullable=False),
        sa.Column("mismatch_count", sa.Integer(), nullable=False),
        sa.Column("max_abs_difference", sa.Integer(), nullable=False),
        sa.Column("is_clean", sa.Boolean(), nullable=False),
        sa.Column("details", details_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("mode IN ('shadow', 'enforce')", name="ck_credit_ledger_run_mode"),
        sa.CheckConstraint("user_count >= 0", name="ck_credit_ledger_run_user_count"),
        sa.CheckConstraint("mismatch_count >= 0", name="ck_credit_ledger_run_mismatch_count"),
        sa.CheckConstraint("max_abs_difference >= 0", name="ck_credit_ledger_run_max_difference"),
    )
    op.create_index(
        "ix_credit_ledger_runs_created",
        "credit_ledger_reconciliation_runs",
        ["created_at"],
    )

    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute(
            """
            INSERT INTO credit_ledger_entries (
                id, user_id, delta, origin, reason, idempotency_key,
                balance_after, created_at
            )
            SELECT md5(random()::text || clock_timestamp()::text)::uuid,
                   id, credits, 'backfill', 'initial balance at ledger activation',
                   'backfill:' || id::text, credits, now()
            FROM users WHERE credits <> 0
            """
        )
        _create_postgres_triggers()
    elif dialect == "sqlite":
        op.execute(
            f"""
            INSERT INTO credit_ledger_entries (
                id, user_id, delta, origin, reason, idempotency_key,
                balance_after, created_at
            )
            SELECT {_SQLITE_UUID}, id, credits, 'backfill',
                   'initial balance at ledger activation',
                   'backfill:' || id, credits, CURRENT_TIMESTAMP
            FROM users WHERE credits <> 0
            """
        )
        _create_sqlite_triggers()


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS credit_ledger_users_update ON users")
        op.execute("DROP TRIGGER IF EXISTS credit_ledger_users_insert ON users")
        op.execute("DROP FUNCTION IF EXISTS clipia_record_credit_projection_change()")
        op.execute("DROP TRIGGER IF EXISTS credit_ledger_entries_append_only ON credit_ledger_entries")
        op.execute("DROP FUNCTION IF EXISTS clipia_reject_credit_ledger_mutation()")
    elif dialect == "sqlite":
        for trigger_name in (
            "credit_ledger_users_update",
            "credit_ledger_users_insert",
            "credit_ledger_entries_no_update",
            "credit_ledger_entries_no_delete",
        ):
            op.execute(f"DROP TRIGGER IF EXISTS {trigger_name}")

    op.drop_index("ix_credit_ledger_runs_created", table_name="credit_ledger_reconciliation_runs")
    op.drop_table("credit_ledger_reconciliation_runs")
    op.drop_index("ix_credit_ledger_origin_created", table_name="credit_ledger_entries")
    op.drop_index("ix_credit_ledger_user_created", table_name="credit_ledger_entries")
    op.drop_table("credit_ledger_entries")
