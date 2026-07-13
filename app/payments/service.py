import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Callable
from urllib.parse import urlsplit
from uuid import UUID

import mercadopago
import stripe
from sqlalchemy import case, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.service import append_server_event_safely
from app.config import settings
from app.credits import public_package_intent
from app.db.models import CreditPurchase, ProcessedPaymentEvent, User
from app.observability import record_credit_metric
from app.payments.schemas import CREDIT_PACKAGES  # noqa: F401 - compatibility export
from app.payments.snapshot import validate_snapshot_metadata
from app.payments.states import canonical_payment_state, payment_state_values
from app.services.credit_ledger import set_credit_ledger_context
from app.utils.locks import get_lock

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PaymentEventResult:
    applied: bool
    balance_delta: int
    state: str | None

    def __bool__(self) -> bool:
        """Keep truthiness compatibility while exposing unambiguous details."""
        return self.applied


def _not_applied(state: str | None = None) -> PaymentEventResult:
    return PaymentEventResult(applied=False, balance_delta=0, state=state)


def _get_sdk() -> mercadopago.SDK:
    return mercadopago.SDK(settings.MP_ACCESS_TOKEN)


def _uuid(value: object) -> UUID | None:
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def _money_to_cents(value: object) -> int | None:
    try:
        cents = Decimal(str(value)) * 100
    except (InvalidOperation, TypeError, ValueError):
        return None
    if cents != cents.to_integral_value():
        return None
    return int(cents)


async def _apply_payment_event(
    db: AsyncSession,
    *,
    purchase_id: UUID,
    provider: str,
    event_key: str,
    event_type: str,
    transition: str,
    external_payment_id: str | None,
    external_checkout_id: str | None,
    validate: Callable[[CreditPurchase], bool],
) -> PaymentEventResult:
    """Validate, claim and apply one normalized provider event atomically."""
    delta = 0
    applied = False
    result_state: str | None = None
    metric_user_id: UUID | None = None
    async with get_lock(f"payment:purchase:{purchase_id}"):
        try:
            row = await db.execute(select(CreditPurchase).where(CreditPurchase.id == purchase_id).with_for_update())
            purchase = row.scalar_one_or_none()
            if purchase is None:
                await db.rollback()
                return _not_applied()

            try:
                current_state = canonical_payment_state(purchase.status, purchase.payment_state)
                result_state = current_state
            except ValueError:
                logger.warning(
                    "Purchase %s has unsupported payment states status=%s payment_state=%s",
                    purchase.id,
                    purchase.status,
                    purchase.payment_state,
                )
                await db.rollback()
                return _not_applied()

            if not validate(purchase):
                await db.rollback()
                return _not_applied(current_state)

            claimed = await db.get(
                ProcessedPaymentEvent,
                {"provider": provider, "event_key": event_key},
            )
            if claimed is not None:
                await db.rollback()
                return _not_applied(current_state)

            if purchase.credits_amount <= 0 or purchase.bonus_credits < 0 or purchase.price_brl <= 0:
                logger.error("Purchase %s has invalid frozen financial values", purchase.id)
                await db.rollback()
                return _not_applied(current_state)

            normalized_checkout_id = str(external_checkout_id).strip() if external_checkout_id else None
            normalized_payment_id = str(external_payment_id).strip() if external_payment_id else None
            stored_checkout_id = (
                str(purchase.mp_preference_id).strip()
                if purchase.mp_preference_id not in (None, "", "pending")
                else None
            )
            if normalized_checkout_id and stored_checkout_id and stored_checkout_id != normalized_checkout_id:
                await db.rollback()
                return _not_applied(current_state)
            if normalized_payment_id and purchase.mp_payment_id and purchase.mp_payment_id != normalized_payment_id:
                await db.rollback()
                return _not_applied(current_state)

            if normalized_checkout_id:
                checkout_collision = await db.scalar(
                    select(CreditPurchase.id).where(
                        CreditPurchase.provider == provider,
                        CreditPurchase.mp_preference_id == normalized_checkout_id,
                        CreditPurchase.id != purchase.id,
                    )
                )
                if checkout_collision is not None:
                    await db.rollback()
                    return _not_applied(current_state)
            if normalized_payment_id:
                payment_collision = await db.scalar(
                    select(CreditPurchase.id).where(
                        CreditPurchase.provider == provider,
                        CreditPurchase.mp_payment_id == normalized_payment_id,
                        CreditPurchase.id != purchase.id,
                    )
                )
                if payment_collision is not None:
                    await db.rollback()
                    return _not_applied(current_state)

            db.add(
                ProcessedPaymentEvent(
                    provider=provider,
                    event_key=event_key,
                    purchase_id=purchase.id,
                    event_type=event_type,
                )
            )
            await db.flush()

            total = purchase.credits_amount + purchase.bonus_credits
            if transition == "paid" and current_state in {"pending", "void"}:
                for field, value in payment_state_values("paid").items():
                    setattr(purchase, field, value)
                purchase.paid_at = datetime.now(timezone.utc)
                purchase.mp_payment_id = normalized_payment_id
                if normalized_checkout_id:
                    purchase.mp_preference_id = normalized_checkout_id
                delta = total
                applied = True
                result_state = "paid"
            elif transition == "refunded" and current_state in {"pending", "void", "paid"}:
                for field, value in payment_state_values("refunded").items():
                    setattr(purchase, field, value)
                purchase.mp_payment_id = normalized_payment_id
                if normalized_checkout_id:
                    purchase.mp_preference_id = normalized_checkout_id
                if current_state == "paid":
                    delta = -total
                applied = True
                result_state = "refunded"
            elif transition == "void" and current_state == "pending":
                for field, value in payment_state_values("void").items():
                    setattr(purchase, field, value)
                if normalized_checkout_id:
                    purchase.mp_preference_id = normalized_checkout_id
                applied = True
                result_state = "void"
            elif transition not in {"paid", "refunded", "void"}:
                raise ValueError(f"Unsupported payment transition: {transition}")

            metric_user_id = purchase.user_id
            if delta > 0:
                await set_credit_ledger_context(
                    db,
                    origin="payment_credit",
                    reason="validated paid purchase credited",
                    idempotency_key=f"payment:{purchase.id}:paid",
                    purchase_id=purchase.id,
                )
                await db.execute(
                    update(User)
                    .where(User.id == purchase.user_id)
                    .values(credits=User.credits + delta)
                    .execution_options(synchronize_session=False)
                )
            elif delta < 0:
                await set_credit_ledger_context(
                    db,
                    origin="payment_refund",
                    reason="terminally refunded purchase debited",
                    idempotency_key=f"payment:{purchase.id}:refunded",
                    purchase_id=purchase.id,
                )
                await db.execute(
                    update(User)
                    .where(User.id == purchase.user_id)
                    .values(
                        credits=case(
                            (User.credits + delta < 0, 0),
                            else_=User.credits + delta,
                        )
                    )
                    .execution_options(synchronize_session=False)
                )

            if applied:
                analytics_user = await db.get(User, purchase.user_id)
                if analytics_user is not None:
                    event_at = purchase.paid_at or datetime.now(timezone.utc)
                    total_credits = purchase.credits_amount + purchase.bonus_credits
                    if result_state == "paid":
                        await append_server_event_safely(
                            db,
                            event_name="payment_completed",
                            user=analytics_user,
                            properties={
                                "provider": provider,
                                "package": public_package_intent(purchase.package_name),
                                "total_credits": total_credits,
                            },
                            idempotency_key=f"purchase:{purchase.id}:paid",
                            occurred_at=event_at,
                        )
                    if delta:
                        await append_server_event_safely(
                            db,
                            event_name="credit_balance_changed",
                            user=analytics_user,
                            properties={
                                "reason": "purchase" if delta > 0 else "refund",
                                "delta": delta,
                            },
                            idempotency_key=(
                                f"purchase:{purchase.id}:credit" if delta > 0 else f"purchase:{purchase.id}:refund"
                            ),
                            occurred_at=event_at,
                        )

            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            try:
                duplicate = await db.get(
                    ProcessedPaymentEvent,
                    {"provider": provider, "event_key": event_key},
                )
                duplicate_purchase_id = duplicate.purchase_id if duplicate is not None else None
                identity_collision = None
                if external_payment_id:
                    identity_collision = await db.scalar(
                        select(CreditPurchase.id).where(
                            CreditPurchase.provider == provider,
                            CreditPurchase.mp_payment_id == str(external_payment_id),
                            CreditPurchase.id != purchase_id,
                        )
                    )
                if identity_collision is None and external_checkout_id:
                    identity_collision = await db.scalar(
                        select(CreditPurchase.id).where(
                            CreditPurchase.provider == provider,
                            CreditPurchase.mp_preference_id == str(external_checkout_id),
                            CreditPurchase.id != purchase_id,
                        )
                    )
                await db.rollback()
            except Exception:
                await db.rollback()
                logger.exception(
                    "Failed to verify payment event claim after IntegrityError "
                    "(provider=%s, event_key=%s, purchase=%s)",
                    provider,
                    event_key,
                    purchase_id,
                )
                raise exc
            if duplicate_purchase_id == purchase_id:
                return _not_applied(result_state)
            if identity_collision is not None:
                logger.warning(
                    "Provider identity collision rejected (provider=%s, purchase=%s, conflicting_purchase=%s)",
                    provider,
                    purchase_id,
                    identity_collision,
                )
                return _not_applied(result_state)
            logger.error(
                "Payment event IntegrityError without matching claim "
                "(provider=%s, event_key=%s, purchase=%s, claimed_purchase=%s)",
                provider,
                event_key,
                purchase_id,
                duplicate_purchase_id,
                exc_info=(type(exc), exc, exc.__traceback__),
            )
            raise
        except Exception:
            await db.rollback()
            raise

    if delta > 0:
        record_credit_metric("credit", delta)
    elif delta < 0:
        record_credit_metric("debit", -delta)
    if delta:
        logger.info(
            "Applied payment delta %d to user %s (purchase %s, provider=%s)",
            delta,
            metric_user_id,
            purchase_id,
            provider,
        )
    return PaymentEventResult(applied=applied, balance_delta=delta, state=result_state)


async def _checkout_legacy_result(
    user: User,
    package_key: str,
    provider: str,
    db: AsyncSession,
    request_key: str | None,
) -> tuple[str, UUID]:
    from app.payments.checkout_outbox import (
        CheckoutFailed,
        CheckoutPending,
        create_or_resume_checkout,
    )

    outcome = await create_or_resume_checkout(
        user,
        package_key,
        provider,
        db,
        request_key=request_key,
    )
    if outcome.state == "ready" and outcome.checkout_url:
        return outcome.checkout_url, outcome.purchase_id
    if outcome.state == "pending":
        raise CheckoutPending(outcome)
    raise CheckoutFailed(outcome, detail=outcome.error_detail or "checkout dispatch failed")


async def create_checkout(
    user: User,
    package_key: str,
    db: AsyncSession,
    request_key: str | None = None,
) -> tuple[str, UUID]:
    """Create/resume a durable MP checkout while preserving the ready tuple API."""
    return await _checkout_legacy_result(user, package_key, "mercadopago", db, request_key)


async def process_webhook(payment_id: str, db: AsyncSession) -> PaymentEventResult:
    """Re-query and apply an authoritative Mercado Pago payment."""
    sdk = _get_sdk()
    try:
        result = await asyncio.to_thread(sdk.payment().get, int(payment_id))
        payment = _to_plain(result["response"])
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning("Invalid Mercado Pago response for %s: %s", payment_id, exc)
        return _not_applied()

    mp_status = payment.get("status")
    if mp_status == "approved":
        transition = "paid"
    elif mp_status in ("refunded", "charged_back"):
        transition = "refunded"
    elif mp_status in ("cancelled", "canceled", "rejected"):
        transition = "void"
    else:
        return _not_applied()

    purchase_id = _uuid(payment.get("external_reference"))
    authoritative_id = payment.get("id")
    amount_cents = _money_to_cents(payment.get("transaction_amount"))
    currency = payment.get("currency_id")
    preference_id = payment.get("preference_id")
    if (
        purchase_id is None
        or authoritative_id is None
        or str(authoritative_id) != str(payment_id)
        or amount_cents is None
        or str(currency).upper() != "BRL"
    ):
        logger.warning("Mercado Pago authoritative validation failed for payment %s", payment_id)
        return _not_applied()

    preview = await db.get(CreditPurchase, purchase_id)
    if preview is None:
        await db.rollback()
        return _not_applied()

    metadata = _to_plain(payment.get("metadata") or {})
    proven_checkout_id: str | None = None
    if preview.snapshot_version == 1:
        if not validate_snapshot_metadata(preview, metadata):
            await db.rollback()
            logger.warning("Mercado Pago snapshot metadata mismatch for payment %s", payment_id)
            return _not_applied()
        proven_checkout_id = str(preference_id or "").strip() or None
        stored_checkout_id = (
            str(preview.mp_preference_id).strip() if preview.mp_preference_id not in (None, "", "pending") else None
        )
        if proven_checkout_id is None or (stored_checkout_id and proven_checkout_id != stored_checkout_id):
            await db.rollback()
            return _not_applied()
    elif preview.snapshot_version is None:
        stored_checkout_id = (
            str(preview.mp_preference_id).strip() if preview.mp_preference_id not in (None, "", "pending") else None
        )
        if stored_checkout_id is None:
            await db.rollback()
            return _not_applied()
        if preference_id is not None:
            if str(preference_id) != stored_checkout_id:
                await db.rollback()
                return _not_applied()
            proven_checkout_id = stored_checkout_id
        else:
            order = payment.get("order")
            order_id = order.get("id") if isinstance(order, dict) else None
            if order_id is None:
                await db.rollback()
                return _not_applied()
            try:
                merchant_result = await asyncio.to_thread(_get_sdk().merchant_order().get, order_id)
                merchant_order = _to_plain(merchant_result["response"])
            except Exception as exc:  # noqa: BLE001
                await db.rollback()
                logger.warning("Mercado Pago merchant order proof failed for payment %s: %s", payment_id, exc)
                return _not_applied()
            payments = merchant_order.get("payments")
            payment_ids = (
                {str(item.get("id")) for item in payments if isinstance(item, dict) and item.get("id") is not None}
                if isinstance(payments, list)
                else set()
            )
            if (
                str(merchant_order.get("id")) != str(order_id)
                or str(merchant_order.get("preference_id")) != stored_checkout_id
                or str(authoritative_id) not in payment_ids
            ):
                await db.rollback()
                return _not_applied()
            proven_checkout_id = stored_checkout_id
    else:
        await db.rollback()
        return _not_applied()
    await db.rollback()

    def validate(purchase: CreditPurchase) -> bool:
        return (
            purchase.provider == "mercadopago"
            and purchase.price_brl == amount_cents
            and str(purchase.currency).upper() == str(currency).upper()
            and (
                validate_snapshot_metadata(purchase, metadata)
                if purchase.snapshot_version == 1
                else purchase.snapshot_version is None
                and purchase.mp_preference_id not in (None, "", "pending")
                and str(purchase.mp_preference_id) == str(proven_checkout_id)
            )
            and (purchase.mp_payment_id is None or purchase.mp_payment_id == str(authoritative_id))
        )

    return await _apply_payment_event(
        db,
        purchase_id=purchase_id,
        provider="mercadopago",
        event_key=f"payment:{authoritative_id}:{mp_status}",
        event_type=str(mp_status),
        transition=transition,
        external_payment_id=None if transition == "void" else str(authoritative_id),
        external_checkout_id=proven_checkout_id,
        validate=validate,
    )


_STRIPE_PAID_EVENTS = ("checkout.session.completed", "checkout.session.async_payment_succeeded")
_STRIPE_VOID_EVENTS = ("checkout.session.expired", "checkout.session.async_payment_failed")

_STRIPE_CHECKOUT_ID_RE = re.compile(r"^cs_(?:test|live)_[A-Za-z0-9]{8,}$")
_MP_PREFERENCE_ID_RE = re.compile(r"^[0-9]{1,20}-[A-Za-z0-9][A-Za-z0-9-]{15,199}$")
_STRIPE_CHECKOUT_HOSTS = frozenset({"checkout.stripe.com"})
_MP_CHECKOUT_HOSTS = frozenset(
    {
        "www.mercadopago.com",
        "sandbox.mercadopago.com",
        "www.mercadopago.com.br",
        "sandbox.mercadopago.com.br",
    }
)


def _valid_checkout_url(value: str, allowed_hosts: frozenset[str]) -> bool:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except (TypeError, ValueError):
        return False
    return (
        parsed.scheme.lower() == "https"
        and parsed.hostname is not None
        and parsed.hostname.lower() in allowed_hosts
        and parsed.username is None
        and parsed.password is None
        and port is None
    )


def _valid_checkout_response(provider: str, checkout_id: str, checkout_url: str) -> bool:
    if provider == "stripe":
        return bool(_STRIPE_CHECKOUT_ID_RE.fullmatch(checkout_id)) and _valid_checkout_url(
            checkout_url, _STRIPE_CHECKOUT_HOSTS
        )
    if provider == "mercadopago":
        return bool(_MP_PREFERENCE_ID_RE.fullmatch(checkout_id)) and _valid_checkout_url(
            checkout_url, _MP_CHECKOUT_HOSTS
        )
    return False


def _init_stripe() -> None:
    stripe.api_key = settings.STRIPE_SECRET_KEY


def _to_plain(obj) -> dict:
    """Normalize Stripe SDK objects while leaving dict test doubles unchanged."""
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    return dict(obj)


async def create_checkout_stripe(
    user: User,
    package_key: str,
    db: AsyncSession,
    request_key: str | None = None,
) -> tuple[str, UUID]:
    """Create/resume a durable Stripe checkout while preserving the ready tuple API."""
    return await _checkout_legacy_result(user, package_key, "stripe", db, request_key)


async def verify_stripe_event_via_api(parsed: dict) -> dict | None:
    """Re-query the provider object when no Stripe webhook secret is configured."""
    etype = parsed.get("type")
    obj = parsed.get("data", {}).get("object", {})
    _init_stripe()
    try:
        if etype in _STRIPE_PAID_EVENTS:
            sid = obj.get("id")
            if not sid:
                return None
            session = await asyncio.to_thread(stripe.checkout.Session.retrieve, sid)
            authoritative = _to_plain(session)
            if str(authoritative.get("id")) != str(sid):
                return None
            return {"type": etype, "data": {"object": authoritative}}
        if etype == "checkout.session.expired":
            sid = obj.get("id")
            if not sid:
                return None
            session = await asyncio.to_thread(stripe.checkout.Session.retrieve, sid)
            authoritative = _to_plain(session)
            if str(authoritative.get("id")) != str(sid) or authoritative.get("status") != "expired":
                return None
            return {"type": etype, "data": {"object": authoritative}}
        if etype == "checkout.session.async_payment_failed":
            # Session complete+unpaid is also the normal state while an async
            # payment is still pending. Without a signed event, fail closed.
            return None
        if etype == "charge.refunded":
            charge_id = obj.get("id")
            if not charge_id:
                return None
            charge = await asyncio.to_thread(stripe.Charge.retrieve, charge_id)
            authoritative = _to_plain(charge)
            if str(authoritative.get("id")) != str(charge_id):
                return None
            return {"type": etype, "data": {"object": authoritative}}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Stripe verify via API failed: %s", exc)
        return None
    return None


async def process_webhook_stripe(event: dict, db: AsyncSession) -> PaymentEventResult:
    """Apply a signed or provider-retrieved Stripe event."""
    event = _to_plain(event)
    etype = event.get("type")
    obj = _to_plain(event.get("data", {}).get("object", {}))

    if etype in (*_STRIPE_PAID_EVENTS, *_STRIPE_VOID_EVENTS):
        metadata = _to_plain(obj.get("metadata") or {})
        client_purchase_id = obj.get("client_reference_id")
        metadata_purchase_id = metadata.get("purchase_id")
        if client_purchase_id and metadata_purchase_id and str(client_purchase_id) != str(metadata_purchase_id):
            logger.warning("Stripe session has divergent purchase ids: %s", obj.get("id"))
            return _not_applied()
        purchase_id = _uuid(client_purchase_id or metadata_purchase_id)
        session_id = obj.get("id")
        payment_intent = obj.get("payment_intent")
        if isinstance(payment_intent, dict):
            payment_intent = payment_intent.get("id")
        is_paid_event = etype in _STRIPE_PAID_EVENTS
        if purchase_id is None or not session_id or (is_paid_event and not payment_intent):
            logger.warning("Stripe session missing financial identity: %s", session_id)
            return _not_applied()
        event_key = str(event.get("id") or f"api:{etype}:{session_id}")

        def validate(purchase: CreditPurchase) -> bool:
            stored_checkout_id = (
                str(purchase.mp_preference_id) if purchase.mp_preference_id not in (None, "", "pending") else None
            )
            metadata_matches = (
                validate_snapshot_metadata(purchase, metadata)
                if purchase.snapshot_version == 1
                else purchase.snapshot_version is None and metadata.get("purchase_id") == str(purchase.id)
            )
            return (
                (obj.get("payment_status") == "paid" if is_paid_event else obj.get("payment_status") != "paid")
                and purchase.provider == "stripe"
                and metadata_matches
                and (
                    stored_checkout_id == str(session_id)
                    or (stored_checkout_id is None and purchase.snapshot_version == 1)
                )
                and obj.get("amount_total") == purchase.price_brl
                and str(obj.get("currency", "")).upper() == str(purchase.currency).upper()
                and (purchase.mp_payment_id is None or purchase.mp_payment_id == str(payment_intent))
            )

        return await _apply_payment_event(
            db,
            purchase_id=purchase_id,
            provider="stripe",
            event_key=event_key,
            event_type=str(etype),
            transition="paid" if is_paid_event else "void",
            external_payment_id=str(payment_intent) if is_paid_event else None,
            external_checkout_id=str(session_id),
            validate=validate,
        )

    if etype == "charge.refunded":
        payment_intent = obj.get("payment_intent")
        if isinstance(payment_intent, dict):
            payment_intent = payment_intent.get("id")
        if not payment_intent:
            return _not_applied()
        _init_stripe()
        try:
            payment_intent_obj = _to_plain(await asyncio.to_thread(stripe.PaymentIntent.retrieve, str(payment_intent)))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Stripe PaymentIntent retrieve failed for refund: %s", exc)
            return _not_applied()
        if payment_intent_obj.get("id") != str(payment_intent):
            return _not_applied()

        metadata = _to_plain(payment_intent_obj.get("metadata") or {})
        metadata_purchase_id = metadata.get("purchase_id")
        purchase_id = _uuid(metadata_purchase_id) if metadata_purchase_id else None
        if metadata_purchase_id and purchase_id is None:
            logger.warning("Stripe PaymentIntent has invalid purchase_id metadata")
            return _not_applied()
        if purchase_id is None:
            row = await db.execute(
                select(CreditPurchase.id).where(
                    CreditPurchase.mp_payment_id == str(payment_intent),
                    CreditPurchase.provider == "stripe",
                )
            )
            candidates = row.scalars().all()
            await db.rollback()
            if len(candidates) != 1:
                return _not_applied()
            purchase_id = candidates[0]

        charge_id = obj.get("id")
        if not charge_id:
            return _not_applied()
        event_key = str(event.get("id") or f"api:{etype}:{charge_id}")

        def validate(purchase: CreditPurchase) -> bool:
            if obj.get("amount_refunded") != purchase.price_brl:
                logger.warning(
                    "Stripe partial refund requires reconciliation (purchase=%s, refunded=%s, total=%s)",
                    purchase.id,
                    obj.get("amount_refunded"),
                    purchase.price_brl,
                )
                return False
            return (
                purchase.provider == "stripe"
                and obj.get("amount") == purchase.price_brl
                and str(obj.get("currency", "")).upper() == str(purchase.currency).upper()
                and obj.get("refunded") is True
                and (
                    validate_snapshot_metadata(purchase, metadata)
                    if purchase.snapshot_version == 1
                    else purchase.snapshot_version is None
                    and (not metadata or metadata.get("purchase_id") == str(purchase.id))
                )
                and (purchase.mp_payment_id is None or purchase.mp_payment_id == str(payment_intent))
            )

        return await _apply_payment_event(
            db,
            purchase_id=purchase_id,
            provider="stripe",
            event_key=event_key,
            event_type=str(etype),
            transition="refunded",
            external_payment_id=str(payment_intent),
            external_checkout_id=None,
            validate=validate,
        )

    return _not_applied()
