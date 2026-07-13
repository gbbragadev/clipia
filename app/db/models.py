import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID, JsonType


class CreditPurchase(Base):
    __tablename__ = "credit_purchases"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'paid', 'refunded', 'charged_back', "
            "'cancelled', 'canceled', 'rejected', 'expired', 'void')",
            name="ck_credit_purchase_legacy_status",
        ),
        CheckConstraint("credits_amount > 0", name="ck_credit_purchase_credits_positive"),
        CheckConstraint("bonus_credits >= 0", name="ck_credit_purchase_bonus_nonnegative"),
        CheckConstraint("price_brl > 0", name="ck_credit_purchase_price_positive"),
        CheckConstraint(
            "payment_state IS NULL OR payment_state IN ('pending', 'paid', 'refunded', 'void')",
            name="ck_credit_purchase_payment_state",
        ),
        CheckConstraint(
            "snapshot_version IS NULL OR snapshot_version = 1",
            name="ck_credit_purchase_snapshot_version",
        ),
        CheckConstraint(
            "(snapshot_version IS NULL AND snapshot_hash IS NULL) OR "
            "(snapshot_version = 1 AND snapshot_hash IS NOT NULL AND LENGTH(snapshot_hash) = 64)",
            name="ck_credit_purchase_snapshot_pair",
        ),
        Index(
            "uq_credit_purchase_provider_checkout",
            "provider",
            "mp_preference_id",
            unique=True,
            postgresql_where=text("mp_preference_id IS NOT NULL AND mp_preference_id <> 'pending'"),
            sqlite_where=text("mp_preference_id IS NOT NULL AND mp_preference_id <> 'pending'"),
        ),
        Index(
            "uq_credit_purchase_provider_payment",
            "provider",
            "mp_payment_id",
            unique=True,
            postgresql_where=text("mp_payment_id IS NOT NULL"),
            sqlite_where=text("mp_payment_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    package_name: Mapped[str] = mapped_column(String(50), nullable=False)
    credits_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    # Bonus promocional creditado JUNTO com credits_amount no momento da aprovacao (snapshot da
    # flag PURCHASE_BONUS_PERCENT na epoca da compra) — estorno reverte base+bonus mesmo se a
    # promo ja tiver acabado.
    bonus_credits: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    price_brl: Mapped[int] = mapped_column(Integer, nullable=False)  # centavos
    provider: Mapped[str] = mapped_column(
        String(20), nullable=False, default="mercadopago", server_default="mercadopago"
    )
    # ponytail: nomes mp_* mantidos por compatibilidade; guardam o id do checkout/pagamento do provider
    # ATIVO (MP: preference_id/payment_id; Stripe: session_id/payment_intent_id). Renomear = churn em 8
    # call-sites + export de conta + 4 testes, sem ganho funcional. provider diz qual gateway é.
    mp_payment_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mp_preference_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    payment_state: Mapped[str | None] = mapped_column(String(20), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="BRL", server_default="BRL")
    snapshot_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    snapshot_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="purchases")


class PaymentCheckoutDispatch(Base):
    """Durable authority for creating and binding one provider checkout."""

    __tablename__ = "payment_checkout_dispatches"
    __table_args__ = (
        UniqueConstraint("purchase_id", name="uq_payment_checkout_dispatch_purchase"),
        UniqueConstraint(
            "provider_idempotency_key",
            name="uq_payment_checkout_dispatch_provider_key",
        ),
        UniqueConstraint("request_key", name="uq_payment_checkout_dispatch_request_key"),
        CheckConstraint(
            "provider IN ('stripe', 'mercadopago')",
            name="ck_payment_checkout_dispatch_provider",
        ),
        CheckConstraint(
            "state IN ('pending', 'ready', 'failed', 'cancelled')",
            name="ck_payment_checkout_dispatch_state",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_payment_checkout_dispatch_attempts"),
        CheckConstraint(
            "LENGTH(request_payload_hash) = 64",
            name="ck_payment_checkout_dispatch_payload_hash",
        ),
        CheckConstraint(
            "request_key IS NULL OR LENGTH(request_key) = 64",
            name="ck_payment_checkout_dispatch_request_key",
        ),
        CheckConstraint(
            "request_fingerprint IS NULL OR LENGTH(request_fingerprint) = 64",
            name="ck_payment_checkout_dispatch_fingerprint",
        ),
        CheckConstraint(
            "(request_key IS NULL AND request_fingerprint IS NULL) OR "
            "(request_key IS NOT NULL AND request_fingerprint IS NOT NULL)",
            name="ck_payment_checkout_dispatch_request_pair",
        ),
        CheckConstraint(
            "(publisher_token IS NULL AND publisher_lease_until IS NULL) OR "
            "(publisher_token IS NOT NULL AND publisher_lease_until IS NOT NULL)",
            name="ck_payment_checkout_dispatch_lease_pair",
        ),
        CheckConstraint(
            "error_code IS NULL OR error_code IN "
            "('provider_unavailable', 'rate_limited', 'provider_rejected', "
            "'invalid_response', 'identity_collision', 'payload_corrupt', "
            "'config_invalid', 'purchase_terminal', 'binding_failed')",
            name="ck_payment_checkout_dispatch_error_code",
        ),
        CheckConstraint(
            "(state = 'pending' AND provider_checkout_id IS NULL AND checkout_url IS NULL "
            "AND checkout_expires_at IS NULL AND ready_at IS NULL AND failed_at IS NULL "
            "AND next_attempt_at IS NOT NULL) OR "
            "(state = 'ready' AND provider_checkout_id IS NOT NULL AND checkout_url IS NOT NULL "
            "AND ready_at IS NOT NULL AND failed_at IS NULL AND next_attempt_at IS NULL "
            "AND publisher_token IS NULL AND publisher_lease_until IS NULL "
            "AND error_code IS NULL AND error_detail IS NULL) OR "
            "(state IN ('failed', 'cancelled') AND provider_checkout_id IS NULL AND checkout_url IS NULL "
            "AND checkout_expires_at IS NULL AND ready_at IS NULL AND failed_at IS NOT NULL "
            "AND next_attempt_at IS NULL AND publisher_token IS NULL "
            "AND publisher_lease_until IS NULL AND error_code IS NOT NULL)",
            name="ck_payment_checkout_dispatch_terminal_fields",
        ),
        Index(
            "ix_payment_checkout_dispatch_due",
            "next_attempt_at",
            "created_at",
            postgresql_where=text("state = 'pending'"),
            sqlite_where=text("state = 'pending'"),
        ),
        Index(
            "uq_payment_checkout_dispatch_provider_checkout",
            "provider",
            "provider_checkout_id",
            unique=True,
            postgresql_where=text("provider_checkout_id IS NOT NULL"),
            sqlite_where=text("provider_checkout_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    purchase_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("credit_purchases.id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_payload: Mapped[str] = mapped_column(Text, nullable=False)
    request_payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    publisher_token: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    publisher_lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_checkout_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    checkout_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    checkout_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProcessedPaymentEvent(Base):
    """Minimal idempotency claim for an authoritative provider event."""

    __tablename__ = "processed_payment_events"

    provider: Mapped[str] = mapped_column(String(20), primary_key=True)
    event_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    purchase_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("credit_purchases.id"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CreditAdjustment(Base):
    """Auditoria de ajuste manual de creditos pelo admin (e dinheiro: quem, quanto, por que)."""

    __tablename__ = "credit_adjustments"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    admin_user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    target_user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    previous_balance: Mapped[int] = mapped_column(Integer, nullable=False)
    new_balance: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    credits: Mapped[int] = mapped_column(Integer, default=2)
    script_refine_pending: Mapped[float] = mapped_column(Float, default=0.0, server_default="0", nullable=False)
    script_refine_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    script_refine_redis_migrated: Mapped[bool] = mapped_column(default=False, server_default="false", nullable=False)
    plan: Mapped[str] = mapped_column(String(50), default="free")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    email_verified: Mapped[bool] = mapped_column(default=False)
    verification_code: Mapped[str | None] = mapped_column(String(6), nullable=True)
    verification_expires: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    utm_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    utm_medium: Mapped[str | None] = mapped_column(String(100), nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(String(100), nullable=True)
    otp_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    referral_code: Mapped[str] = mapped_column(
        String(12), unique=True, nullable=False, default=lambda: uuid.uuid4().hex[:8]
    )
    referred_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True)
    password_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # LGPD: comprovante de consentimento expresso no cadastro (Termos + Política de Privacidade).
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consent_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)

    jobs: Mapped[list["Job"]] = relationship(back_populates="user")
    purchases: Mapped[list["CreditPurchase"]] = relationship(back_populates="user")
    voice_clones: Mapped[list["VoiceClone"]] = relationship(back_populates="user")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_rerender_state_debited_at", "rerender_state", "rerender_debited_at"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    topic: Mapped[str] = mapped_column(String(500), nullable=False)
    style: Mapped[str] = mapped_column(String(50), nullable=False)
    duration_target: Mapped[int] = mapped_column(Integer, nullable=False)
    template_id: Mapped[str] = mapped_column(String(50), default="stock_narration")
    # index: fila (WHERE status='queued' em _queue_ahead_of) e agregacoes do admin
    status: Mapped[str] = mapped_column(String(50), default="queued", index=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    current_step: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    script: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    editor_state: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    generation_dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    generation_refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pending_credits: Mapped[float] = mapped_column(Float, default=0.0)
    rerender_operation_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    rerender_state: Mapped[str] = mapped_column(String(20), default="idle", server_default="idle", nullable=False)
    rerender_cost: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    rerender_pending_credits: Mapped[float] = mapped_column(Float, default=0.0, server_default="0", nullable=False)
    rerender_debited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rerender_dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    credit_cost: Mapped[int] = mapped_column(Integer, default=1)
    refine_credit_cost: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    voice_provider: Mapped[str] = mapped_column(String(50), default="edge")
    voice_config: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    # Economia por job (consolidado no finalize): {steps: {etapa: segundos},
    # total_seconds, api_cost_usd_est, credit_cost} — alimenta o admin/economy.
    telemetry: Mapped[dict | None] = mapped_column(JsonType, nullable=True)

    user: Mapped["User"] = relationship(back_populates="jobs")


class JobDispatch(Base):
    """Transactional outbox entry for one paid generation/rerender operation."""

    __tablename__ = "job_dispatches"
    __table_args__ = (
        UniqueConstraint("kind", "operation_id", name="uq_job_dispatch_kind_operation"),
        CheckConstraint("kind IN ('generation', 'rerender')", name="ck_job_dispatch_kind"),
        CheckConstraint(
            "state IN ('pending', 'published', 'claimed', 'completed', 'cancelled')",
            name="ck_job_dispatch_state",
        ),
        CheckConstraint("debited_credits >= 0", name="ck_job_dispatch_debited_credits"),
        CheckConstraint("refine_debited >= 0", name="ck_job_dispatch_refine_debited"),
        CheckConstraint("pending_credits_snapshot >= 0", name="ck_job_dispatch_pending_snapshot"),
        Index("ix_job_dispatch_state_attempt", "state", "last_attempt_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("jobs.id"), nullable=False, index=True)
    operation_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    payload: Mapped[dict] = mapped_column(JsonType, nullable=False)
    debited_credits: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    refine_debited: Mapped[float] = mapped_column(Float, default=0.0, server_default="0", nullable=False)
    pending_credits_snapshot: Mapped[float] = mapped_column(Float, default=0.0, server_default="0", nullable=False)
    state: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending", nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_task_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    publisher_token: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    publisher_lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_task_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    worker_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RefineBalanceOutbox(Base):
    """Versioned projection of the SQL refine balance to the legacy Redis key."""

    __tablename__ = "refine_balance_outbox"
    __table_args__ = (
        UniqueConstraint("user_id", "version", name="uq_refine_balance_outbox_user_version"),
        Index("ix_refine_balance_outbox_applied", "applied_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class VoiceClone(Base):
    __tablename__ = "voice_clones"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), default="elevenlabs")
    external_voice_id: Mapped[str] = mapped_column(String(255), nullable=False)
    samples_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="voice_clones")


class Feedback(Base):
    """Feedback do usuario: widget in-app (nota 1-5 + texto) e prompt pos-video (por job)."""

    __tablename__ = "feedbacks"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # widget | post_video
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-5
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("jobs.id"), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WaitlistEntry(Base):
    __tablename__ = "waitlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
