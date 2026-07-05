import hashlib
import hmac
import json
import logging
from json import JSONDecodeError

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.config import settings
from app.db.engine import get_db
from app.db.models import CreditPurchase, User
from app.payments.schemas import (
    CREDIT_PACKAGES,
    CheckoutRequest,
    CheckoutResponse,
    PackageResponse,
    PurchaseHistoryItem,
    PurchaseHistoryResponse,
)
from app.payments.service import (
    create_checkout,
    create_checkout_stripe,
    process_webhook,
    process_webhook_stripe,
    verify_stripe_event_via_api,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["payments"])


@router.get(
    "/credits/packages",
    response_model=list[PackageResponse],
    summary="List packages",
    description="Returns available credit packages.",
    responses={200: {"description": "List of packages"}},
)
async def list_packages(user: User = Depends(get_current_user)):
    """Get available credit packages."""
    packages = []
    for key, pkg in CREDIT_PACKAGES.items():
        price = pkg["price_brl"]
        reais = price // 100
        centavos = price % 100
        bonus = pkg["credits"] * settings.PURCHASE_BONUS_PERCENT // 100
        packages.append(
            PackageResponse(
                id=key,
                name=pkg["name"],
                credits=pkg["credits"],
                price_brl=price,
                price_display=f"R$ {reais},{centavos:02d}",
                bonus_percent=settings.PURCHASE_BONUS_PERCENT if bonus else 0,
                bonus_credits=bonus,
            )
        )
    return packages


@router.post(
    "/credits/checkout",
    response_model=CheckoutResponse,
    summary="Checkout package",
    description="Creates a checkout URL to buy credits.",
    responses={200: {"description": "Checkout URL"}},
)
async def checkout(
    req: CheckoutRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Initiate a credit purchase via Mercado Pago (default) ou Stripe."""
    if req.package not in CREDIT_PACKAGES:
        raise HTTPException(status_code=400, detail="Pacote invalido")
    if req.provider not in ("mercadopago", "stripe"):
        raise HTTPException(status_code=400, detail="Provedor invalido")

    try:
        if req.provider == "stripe":
            checkout_url, purchase_id = await create_checkout_stripe(user, req.package, db)
        else:
            checkout_url, purchase_id = await create_checkout(user, req.package, db)
    except Exception as e:  # noqa: BLE001
        logger.error("Checkout (%s) falhou: %s", req.provider, e)
        raise HTTPException(
            status_code=502,
            detail="Não foi possível iniciar o pagamento. Tente novamente em instantes.",
        )
    return CheckoutResponse(checkout_url=checkout_url, purchase_id=purchase_id)


@router.post(
    "/webhooks/mercadopago",
    status_code=200,
    summary="Mercado Pago Webhook",
    description="Receives payment updates from MercadoPago.",
    responses={200: {"description": "Processed"}},
)
async def mercadopago_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Process payment webhook."""
    body = await request.body()
    try:
        parsed = json.loads(body)
    except JSONDecodeError:
        logger.warning("Webhook received invalid JSON body")
        return {"status": "invalid_payload"}

    # Validate signature if webhook secret is configured
    if settings.MP_WEBHOOK_SECRET:
        signature = request.headers.get("x-signature", "")
        request_id = request.headers.get("x-request-id", "")

        parts = {}
        for part in signature.split(","):
            if "=" in part:
                k, v = part.split("=", 1)
                parts[k.strip()] = v.strip()

        ts = parts.get("ts", "")
        v1 = parts.get("v1", "")

        if not ts or not v1:
            logger.warning("Webhook missing signature parts: %s", signature)
            return {"status": "invalid_signature"}

        data_id = ""
        if "data" in parsed and "id" in parsed["data"]:
            data_id = str(parsed["data"]["id"])

        manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
        expected = hmac.new(
            settings.MP_WEBHOOK_SECRET.encode(),
            manifest.encode(),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, v1):
            logger.warning("Webhook signature mismatch")
            return {"status": "invalid_signature"}

    action = parsed.get("action") or parsed.get("type")
    if action not in ("payment.created", "payment.updated", "payment"):
        return {"status": "ignored"}

    payment_id = None
    if "data" in parsed and "id" in parsed["data"]:
        payment_id = str(parsed["data"]["id"])
    elif "id" in parsed:
        payment_id = str(parsed["id"])

    if not payment_id:
        logger.warning("Webhook without payment ID: %s", parsed)
        return {"status": "no_payment_id"}

    credited = await process_webhook(payment_id, db)
    return {"status": "credited" if credited else "not_credited"}


@router.post(
    "/webhooks/stripe",
    status_code=200,
    summary="Stripe Webhook",
    description="Receives payment updates from Stripe (Checkout Session + refunds).",
    responses={200: {"description": "Processed"}},
)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Process Stripe payment webhook."""
    payload = await request.body()

    if settings.STRIPE_WEBHOOK_SECRET:
        sig = request.headers.get("stripe-signature", "")
        try:
            event = stripe.Webhook.construct_event(payload, sig, settings.STRIPE_WEBHOOK_SECRET)
        except Exception as e:  # noqa: BLE001 — assinatura invalida / payload malformado
            logger.warning("Stripe webhook invalido: %s", e)
            return {"status": "invalid_signature"}
    else:
        # Sem secret configurado: parse + RE-VERIFICA via API do Stripe antes de confiar (espelha o MP).
        try:
            parsed = json.loads(payload)
        except JSONDecodeError:
            logger.warning("Stripe webhook com JSON invalido")
            return {"status": "invalid_payload"}
        event = await verify_stripe_event_via_api(parsed)
        if event is None:
            return {"status": "unverified"}

    credited = await process_webhook_stripe(event, db)
    return {"status": "credited" if credited else "not_credited"}


@router.get(
    "/credits/history",
    response_model=PurchaseHistoryResponse,
    summary="Purchase history",
    description="Returns a list of user credit purchases.",
    responses={200: {"description": "Purchase history"}},
)
async def purchase_history(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve purchase history."""
    stmt = (
        select(CreditPurchase)
        .where(CreditPurchase.user_id == user.id)
        .order_by(CreditPurchase.created_at.desc())
        .limit(50)
    )
    result = await db.execute(stmt)
    purchases = result.scalars().all()

    return PurchaseHistoryResponse(
        purchases=[
            PurchaseHistoryItem(
                id=p.id,
                package_name=p.package_name,
                credits_amount=p.credits_amount,
                price_brl=p.price_brl,
                status=p.status,
                created_at=p.created_at,
                paid_at=p.paid_at,
            )
            for p in purchases
        ]
    )
