import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

import mercadopago
import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import CreditPurchase, User
from app.observability import record_credit_metric
from app.payments.schemas import CREDIT_PACKAGES
from app.utils.locks import get_lock

logger = logging.getLogger(__name__)


def _get_sdk() -> mercadopago.SDK:
    return mercadopago.SDK(settings.MP_ACCESS_TOKEN)


# ── Crédito/estorno compartilhado (MP e Stripe usam os mesmos, p/ não divergir) ──────────
# Idempotentes por purchase.status; chame SEMPRE sob um lock por pagamento/sessão.


async def _credit_once(db: AsyncSession, purchase: CreditPurchase, external_payment_id: str | None) -> bool:
    """Credita os créditos da compra UMA vez. Retorna True se creditou agora."""
    if purchase.status == "approved":
        return False  # ja creditado -> segundo webhook nao re-credita
    user_row = await db.execute(select(User).where(User.id == purchase.user_id))
    user = user_row.scalar_one()
    purchase.status = "approved"
    if external_payment_id:
        purchase.mp_payment_id = str(external_payment_id)
    purchase.paid_at = datetime.now(timezone.utc)
    user.credits += purchase.credits_amount
    await db.commit()
    record_credit_metric("credit", purchase.credits_amount)
    logger.info(
        "Credited %d credits to user %s (purchase %s, provider=%s)",
        purchase.credits_amount,
        user.id,
        purchase.id,
        purchase.provider,
    )
    return True


async def _revert_once(db: AsyncSession, purchase: CreditPurchase) -> bool:
    """Reverte créditos de uma compra estornada/cancelada UMA vez. Retorna True se reverteu agora."""
    if purchase.status != "approved":
        return False  # nunca creditou -> nada a reverter
    user_row = await db.execute(select(User).where(User.id == purchase.user_id))
    user = user_row.scalar_one()
    purchase.status = "refunded"
    user.credits = max(0, user.credits - purchase.credits_amount)  # clamp em 0 sob o lock
    await db.commit()
    record_credit_metric("debit", purchase.credits_amount)
    logger.warning(
        "Reverted %d credits from user %s (purchase %s, provider=%s)",
        purchase.credits_amount,
        user.id,
        purchase.id,
        purchase.provider,
    )
    return True


async def create_checkout(user: User, package_key: str, db: AsyncSession) -> tuple[str, UUID]:
    """Create MP preference and return (checkout_url, purchase_id)."""
    pkg = CREDIT_PACKAGES[package_key]

    purchase = CreditPurchase(
        user_id=user.id,
        package_name=package_key,
        credits_amount=pkg["credits"],
        price_brl=pkg["price_brl"],
        mp_preference_id="pending",  # updated after MP call
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

    # back_urls and auto_return require HTTPS — only set in production
    frontend = settings.FRONTEND_URL
    if frontend.startswith("https://"):
        preference_data["back_urls"] = {
            "success": f"{frontend}/dashboard/credits?status=success",
            "failure": f"{frontend}/dashboard/credits?status=failure",
            "pending": f"{frontend}/dashboard/credits?status=pending",
        }
        preference_data["auto_return"] = "approved"

    # notification_url must be publicly accessible
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
    """Reconcilia um pagamento contra a API do MP.

    Credita na aprovacao (idempotente por status) e REVERTE em estorno/chargeback/
    cancelamento. Retorna True se o saldo de creditos mudou.
    """
    async with get_lock(f"payment:{payment_id}"):
        sdk = _get_sdk()
        result = await asyncio.to_thread(sdk.payment().get, int(payment_id))
        payment = result["response"]
        mp_status = payment.get("status")

        external_ref = payment.get("external_reference")
        if not external_ref:
            logger.warning("Webhook payment %s has no external_reference", payment_id)
            return False

        purchase_id = UUID(external_ref)
        row = await db.execute(select(CreditPurchase).where(CreditPurchase.id == purchase_id))
        purchase = row.scalar_one_or_none()
        if not purchase:
            logger.warning("CreditPurchase %s not found for payment %s", purchase_id, payment_id)
            return False

        if mp_status == "approved":
            return await _credit_once(db, purchase, payment_id)
        if mp_status in ("refunded", "charged_back", "cancelled"):
            return await _revert_once(db, purchase)
        return False


# ── Stripe (Checkout hospedado: Cartão + Pix) ────────────────────────────────────────────

_STRIPE_PAID_EVENTS = ("checkout.session.completed", "checkout.session.async_payment_succeeded")


def _init_stripe() -> None:
    stripe.api_key = settings.STRIPE_SECRET_KEY


async def create_checkout_stripe(user: User, package_key: str, db: AsyncSession) -> tuple[str, UUID]:
    """Cria uma Stripe Checkout Session e retorna (checkout_url, purchase_id)."""
    if not settings.STRIPE_SECRET_KEY:
        raise ValueError("Stripe nao configurado")
    pkg = CREDIT_PACKAGES[package_key]

    purchase = CreditPurchase(
        user_id=user.id,
        package_name=package_key,
        credits_amount=pkg["credits"],
        price_brl=pkg["price_brl"],
        provider="stripe",
        mp_preference_id="pending",  # recebe o session.id apos a chamada (ver nota no modelo)
        status="pending",
    )
    db.add(purchase)
    await db.flush()

    frontend = settings.FRONTEND_URL
    _init_stripe()
    # Sem payment_method_types: o Stripe usa os metodos HABILITADOS no dashboard (cartao por padrao;
    # Pix aparece automaticamente quando ativado em dashboard.stripe.com/.../payments/settings).
    # Hardcodar ["card","pix"] estourava 400 quando Pix nao esta ativado na conta.
    session = await asyncio.to_thread(
        lambda: stripe.checkout.Session.create(
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": "brl",
                        "product_data": {"name": f"ClipIA - {pkg['name']} ({pkg['credits']} creditos)"},
                        "unit_amount": pkg["price_brl"],  # centavos
                    },
                    "quantity": 1,
                }
            ],
            client_reference_id=str(purchase.id),
            metadata={"purchase_id": str(purchase.id)},
            success_url=f"{frontend}/dashboard/credits?status=success",
            cancel_url=f"{frontend}/dashboard/credits?status=failure",
        )
    )

    purchase.mp_preference_id = session.id
    await db.commit()
    return session.url, purchase.id


async def verify_stripe_event_via_api(parsed: dict) -> dict | None:
    """Sem webhook secret: re-busca o objeto na API do Stripe (autenticado pela secret key) para
    garantir autenticidade antes de creditar — nunca confia no corpo cru do POST. Espelha o MP."""
    etype = parsed.get("type")
    obj = parsed.get("data", {}).get("object", {})
    _init_stripe()
    try:
        if etype in _STRIPE_PAID_EVENTS:
            sid = obj.get("id")
            if not sid:
                return None
            session = await asyncio.to_thread(stripe.checkout.Session.retrieve, sid)
            return {"type": etype, "data": {"object": dict(session)}}
        if etype == "charge.refunded":
            cid = obj.get("id")
            if not cid:
                return None
            charge = await asyncio.to_thread(stripe.Charge.retrieve, cid)
            return {"type": etype, "data": {"object": dict(charge)}}
    except Exception as e:  # noqa: BLE001
        logger.warning("Stripe verify via API falhou: %s", e)
        return None
    return None


async def process_webhook_stripe(event: dict, db: AsyncSession) -> bool:
    """Processa um evento Stripe JÁ CONFIÁVEL (assinatura verificada OU recuperado via API).

    Credita na conclusão do pagamento (idempotente) e reverte em estorno. Pix é assíncrono:
    só credita quando payment_status == 'paid' (no completed ou no async_payment_succeeded)."""
    etype = event.get("type")
    obj = event.get("data", {}).get("object", {})

    if etype in _STRIPE_PAID_EVENTS:
        if obj.get("payment_status") != "paid":
            return False  # Pix pendente: ainda nao pago, nao credita
        purchase_id = obj.get("client_reference_id") or (obj.get("metadata") or {}).get("purchase_id")
        if not purchase_id:
            logger.warning("Stripe session sem purchase_id: %s", obj.get("id"))
            return False
        async with get_lock(f"stripe:purchase:{purchase_id}"):
            purchase = await db.get(CreditPurchase, UUID(purchase_id))
            if not purchase:
                logger.warning("CreditPurchase %s nao encontrada (stripe)", purchase_id)
                return False
            return await _credit_once(db, purchase, obj.get("payment_intent"))

    if etype == "charge.refunded":
        payment_intent = obj.get("payment_intent")
        if not payment_intent:
            return False
        async with get_lock(f"stripe:pi:{payment_intent}"):
            row = await db.execute(
                select(CreditPurchase).where(
                    CreditPurchase.mp_payment_id == str(payment_intent),
                    CreditPurchase.provider == "stripe",
                )
            )
            purchase = row.scalar_one_or_none()
            if not purchase:
                return False
            return await _revert_once(db, purchase)

    return False
