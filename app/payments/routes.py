import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
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
from app.payments.service import create_checkout, process_webhook

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/credits/packages", response_model=list[PackageResponse])
async def list_packages(user: User = Depends(get_current_user)):
    packages = []
    for key, pkg in CREDIT_PACKAGES.items():
        price = pkg["price_brl"]
        reais = price // 100
        centavos = price % 100
        packages.append(
            PackageResponse(
                id=key,
                name=pkg["name"],
                credits=pkg["credits"],
                price_brl=price,
                price_display=f"R$ {reais},{centavos:02d}",
            )
        )
    return packages


@router.post("/credits/checkout", response_model=CheckoutResponse)
async def checkout(
    req: CheckoutRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if req.package not in CREDIT_PACKAGES:
        raise HTTPException(status_code=400, detail="Pacote inválido")

    checkout_url, purchase_id = await create_checkout(user, req.package, db)
    return CheckoutResponse(checkout_url=checkout_url, purchase_id=purchase_id)


@router.post("/webhooks/mercadopago", status_code=200)
async def mercadopago_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    body = await request.json()

    # MP sends different notification types
    action = body.get("action") or body.get("type")
    if action not in ("payment.created", "payment.updated", "payment"):
        return {"status": "ignored"}

    # Extract payment ID from body
    payment_id = None
    if "data" in body and "id" in body["data"]:
        payment_id = str(body["data"]["id"])
    elif "id" in body:
        payment_id = str(body["id"])

    if not payment_id:
        logger.warning("Webhook without payment ID: %s", body)
        return {"status": "no_payment_id"}

    credited = await process_webhook(payment_id, db)
    return {"status": "credited" if credited else "not_credited"}


@router.get("/credits/history", response_model=PurchaseHistoryResponse)
async def purchase_history(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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
