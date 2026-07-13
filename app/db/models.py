import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import GUID, JsonType


class CreditPurchase(Base):
    __tablename__ = "credit_purchases"

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
    mp_preference_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="purchases")


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
