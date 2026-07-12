import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Callable
from uuid import UUID

import mercadopago
import stripe
from sqlalchemy import case, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import CreditPurchase, ProcessedPaymentEvent, User
from app.observability import record_credit_metric
from app.payments.schemas import CREDIT_PACKAGES
from app.utils.locks import get_lock

logger = logging.getLogger(__name__)


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
    validate: Callable[[CreditPurchase], bool],
) -> bool:
    """Validate, claim and apply one normalized provider event atomically."""
    delta = 0
    metric_user_id: UUID | None = None
    async with get_lock(f"payment:purchase:{purchase_id}"):
        try:
            row = await db.execute(select(CreditPurchase).where(CreditPurchase.id == purchase_id).with_for_update())
            purchase = row.scalar_one_or_none()
            if purchase is None or not validate(purchase):
                await db.rollback()
                return False

            claimed = await db.get(
                ProcessedPaymentEvent,
                {"provider": provider, "event_key": event_key},
            )
            if claimed is not None:
                await db.rollback()
                return False

            current_status = purchase.status
            if current_status not in {"pending", "approved", "refunded"}:
                logger.warning("Purchase %s has unsupported status %s", purchase.id, current_status)
                await db.rollback()
                return False

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
            if transition == "approve" and current_status == "pending":
                purchase.status = "approved"
                purchase.paid_at = datetime.now(timezone.utc)
                purchase.mp_payment_id = external_payment_id
                delta = total
            elif transition == "full_refund" and current_status == "pending":
                purchase.status = "refunded"
                purchase.mp_payment_id = external_payment_id
            elif transition == "full_refund" and current_status == "approved":
                purchase.status = "refunded"
                if external_payment_id:
                    purchase.mp_payment_id = external_payment_id
                delta = -total

            metric_user_id = purchase.user_id
            if delta > 0:
                await db.execute(
                    update(User)
                    .where(User.id == purchase.user_id)
                    .values(credits=User.credits + delta)
                    .execution_options(synchronize_session=False)
                )
            elif delta < 0:
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

            await db.commit()
        except IntegrityError:
            await db.rollback()
            return False
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
    return delta != 0


async def create_checkout(user: User, package_key: str, db: AsyncSession) -> tuple[str, UUID]:
    """Create MP preference and return (checkout_url, purchase_id)."""
    pkg = CREDIT_PACKAGES[package_key]

    purchase = CreditPurchase(
        user_id=user.id,
        package_name=package_key,
        credits_amount=pkg["credits"],
        bonus_credits=pkg["credits"] * settings.PURCHASE_BONUS_PERCENT // 100,
        price_brl=pkg["price_brl"],
        mp_preference_id="pending",
        status="pending",
    )
    db.add(purchase)
    await db.flush()

    preference_data: dict = {
        "items": [
            {
                "title": f"ClipIA - {pkg['name']} ({pkg['credits']} creditos)",
                "quantity": 1,
                "unit_price": pkg["price_brl"] / 100,
                "currency_id": "BRL",
            }
        ],
        "external_reference": str(purchase.id),
    }

    frontend = settings.FRONTEND_URL
    if frontend.startswith("https://"):
        preference_data["back_urls"] = {
            "success": f"{frontend}/dashboard/credits?status=success",
            "failure": f"{frontend}/dashboard/credits?status=failure",
            "pending": f"{frontend}/dashboard/credits?status=pending",
        }
        preference_data["auto_return"] = "approved"

    backend_url = settings.BACKEND_URL
    if backend_url and backend_url.startswith("https://"):
        preference_data["notification_url"] = f"{backend_url}/api/v1/webhooks/mercadopago"

    sdk = _get_sdk()
    result = await asyncio.to_thread(sdk.preference().create, preference_data)
    if result["status"] != 201:
        logger.error("MP preference creation failed: %s", result)
        raise ValueError(f"MercadoPago error: {result['response']}")

    response = result["response"]
    purchase.mp_preference_id = response["id"]
    await db.commit()

    checkout_url = response.get("init_point") or response.get("sandbox_init_point", "")
    return checkout_url, purchase.id


async def process_webhook(payment_id: str, db: AsyncSession) -> bool:
    """Re-query and apply an authoritative Mercado Pago payment."""
    sdk = _get_sdk()
    try:
        result = await asyncio.to_thread(sdk.payment().get, int(payment_id))
        payment = _to_plain(result["response"])
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning("Invalid Mercado Pago response for %s: %s", payment_id, exc)
        return False

    mp_status = payment.get("status")
    if mp_status == "approved":
        transition = "approve"
    elif mp_status in ("refunded", "charged_back", "cancelled"):
        transition = "full_refund"
    else:
        return False

    purchase_id = _uuid(payment.get("external_reference"))
    authoritative_id = payment.get("id")
    amount_cents = _money_to_cents(payment.get("transaction_amount"))
    currency = payment.get("currency_id")
    preference_id = payment.get("preference_id")
    order = payment.get("order")
    if preference_id is None and isinstance(order, dict):
        preference_id = order.get("id")
    if (
        purchase_id is None
        or authoritative_id is None
        or str(authoritative_id) != str(payment_id)
        or amount_cents is None
        or str(currency).upper() != "BRL"
    ):
        logger.warning("Mercado Pago authoritative validation failed for payment %s", payment_id)
        return False

    def validate(purchase: CreditPurchase) -> bool:
        return (
            purchase.provider == "mercadopago"
            and purchase.price_brl == amount_cents
            and (preference_id is None or str(preference_id) == purchase.mp_preference_id)
            and (purchase.mp_payment_id is None or purchase.mp_payment_id == str(authoritative_id))
        )

    return await _apply_payment_event(
        db,
        purchase_id=purchase_id,
        provider="mercadopago",
        event_key=f"payment:{authoritative_id}:{mp_status}",
        event_type=str(mp_status),
        transition=transition,
        external_payment_id=str(authoritative_id),
        validate=validate,
    )


_STRIPE_PAID_EVENTS = ("checkout.session.completed", "checkout.session.async_payment_succeeded")


def _init_stripe() -> None:
    stripe.api_key = settings.STRIPE_SECRET_KEY


def _to_plain(obj) -> dict:
    """Normalize Stripe SDK objects while leaving dict test doubles unchanged."""
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    return dict(obj)


async def create_checkout_stripe(user: User, package_key: str, db: AsyncSession) -> tuple[str, UUID]:
    """Create a Stripe Checkout Session and return (checkout_url, purchase_id)."""
    if not settings.STRIPE_SECRET_KEY:
        raise ValueError("Stripe nao configurado")
    pkg = CREDIT_PACKAGES[package_key]

    purchase = CreditPurchase(
        user_id=user.id,
        package_name=package_key,
        credits_amount=pkg["credits"],
        bonus_credits=pkg["credits"] * settings.PURCHASE_BONUS_PERCENT // 100,
        price_brl=pkg["price_brl"],
        provider="stripe",
        mp_preference_id="pending",
        status="pending",
    )
    db.add(purchase)
    await db.flush()

    frontend = settings.FRONTEND_URL
    _init_stripe()
    session = await asyncio.to_thread(
        lambda: stripe.checkout.Session.create(
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": "brl",
                        "product_data": {"name": f"ClipIA - {pkg['name']} ({pkg['credits']} creditos)"},
                        "unit_amount": pkg["price_brl"],
                    },
                    "quantity": 1,
                }
            ],
            client_reference_id=str(purchase.id),
            metadata={"purchase_id": str(purchase.id)},
            payment_intent_data={"metadata": {"purchase_id": str(purchase.id)}},
            success_url=f"{frontend}/dashboard/credits?status=success",
            cancel_url=f"{frontend}/dashboard/credits?status=failure",
        )
    )

    purchase.mp_preference_id = session.id
    await db.commit()
    return session.url, purchase.id


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
            return {"type": etype, "data": {"object": _to_plain(session)}}
        if etype == "charge.refunded":
            charge_id = obj.get("id")
            if not charge_id:
                return None
            charge = await asyncio.to_thread(stripe.Charge.retrieve, charge_id)
            return {"type": etype, "data": {"object": _to_plain(charge)}}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Stripe verify via API failed: %s", exc)
        return None
    return None


async def process_webhook_stripe(event: dict, db: AsyncSession) -> bool:
    """Apply a signed or provider-retrieved Stripe event."""
    event = _to_plain(event)
    etype = event.get("type")
    obj = _to_plain(event.get("data", {}).get("object", {}))

    if etype in _STRIPE_PAID_EVENTS:
        metadata = _to_plain(obj.get("metadata") or {})
        client_purchase_id = obj.get("client_reference_id")
        metadata_purchase_id = metadata.get("purchase_id")
        if client_purchase_id and metadata_purchase_id and str(client_purchase_id) != str(metadata_purchase_id):
            logger.warning("Stripe session has divergent purchase ids: %s", obj.get("id"))
            return False
        purchase_id = _uuid(client_purchase_id or metadata_purchase_id)
        session_id = obj.get("id")
        payment_intent = obj.get("payment_intent")
        if isinstance(payment_intent, dict):
            payment_intent = payment_intent.get("id")
        if purchase_id is None or not session_id or not payment_intent:
            logger.warning("Stripe session missing financial identity: %s", session_id)
            return False
        event_key = str(event.get("id") or f"api:{etype}:{session_id}")

        def validate(purchase: CreditPurchase) -> bool:
            return (
                obj.get("payment_status") == "paid"
                and purchase.provider == "stripe"
                and str(session_id) == purchase.mp_preference_id
                and obj.get("amount_total") == purchase.price_brl
                and str(obj.get("currency", "")).lower() == "brl"
                and (purchase.mp_payment_id is None or purchase.mp_payment_id == str(payment_intent))
            )

        return await _apply_payment_event(
            db,
            purchase_id=purchase_id,
            provider="stripe",
            event_key=event_key,
            event_type=str(etype),
            transition="approve",
            external_payment_id=str(payment_intent),
            validate=validate,
        )

    if etype == "charge.refunded":
        payment_intent = obj.get("payment_intent")
        if isinstance(payment_intent, dict):
            payment_intent = payment_intent.get("id")
        if not payment_intent:
            return False
        _init_stripe()
        try:
            payment_intent_obj = _to_plain(await asyncio.to_thread(stripe.PaymentIntent.retrieve, str(payment_intent)))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Stripe PaymentIntent retrieve failed for refund: %s", exc)
            return False
        if payment_intent_obj.get("id") not in (None, str(payment_intent)):
            return False

        metadata = _to_plain(payment_intent_obj.get("metadata") or {})
        metadata_purchase_id = metadata.get("purchase_id")
        purchase_id = _uuid(metadata_purchase_id) if metadata_purchase_id else None
        if metadata_purchase_id and purchase_id is None:
            logger.warning("Stripe PaymentIntent has invalid purchase_id metadata")
            return False
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
                return False
            purchase_id = candidates[0]

        charge_id = obj.get("id")
        if not charge_id:
            return False
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
                and str(obj.get("currency", "")).lower() == "brl"
                and obj.get("refunded") is True
                and (purchase.mp_payment_id is None or purchase.mp_payment_id == str(payment_intent))
            )

        return await _apply_payment_event(
            db,
            purchase_id=purchase_id,
            provider="stripe",
            event_key=event_key,
            event_type=str(etype),
            transition="full_refund",
            external_payment_id=str(payment_intent),
            validate=validate,
        )

    return False
