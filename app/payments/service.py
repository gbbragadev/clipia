import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

import mercadopago
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import CreditPurchase, User
from app.payments.schemas import CREDIT_PACKAGES

logger = logging.getLogger(__name__)


def _get_sdk() -> mercadopago.SDK:
    return mercadopago.SDK(settings.MP_ACCESS_TOKEN)


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
    """Fetch payment from MP API and credit user if approved. Returns True if credited."""
    sdk = _get_sdk()
    result = await asyncio.to_thread(sdk.payment().get, int(payment_id))
    payment = result["response"]

    if payment.get("status") != "approved":
        return False

    external_ref = payment.get("external_reference")
    if not external_ref:
        logger.warning("Webhook payment %s has no external_reference", payment_id)
        return False

    purchase_id = UUID(external_ref)
    stmt = select(CreditPurchase).where(CreditPurchase.id == purchase_id)
    row = await db.execute(stmt)
    purchase = row.scalar_one_or_none()

    if not purchase:
        logger.warning("CreditPurchase %s not found for payment %s", purchase_id, payment_id)
        return False

    # Idempotency: already credited
    if purchase.status == "approved":
        return False

    purchase.status = "approved"
    purchase.mp_payment_id = str(payment_id)
    purchase.paid_at = datetime.now(timezone.utc)

    # Credit user
    user_stmt = select(User).where(User.id == purchase.user_id)
    user_row = await db.execute(user_stmt)
    user = user_row.scalar_one()
    user.credits += purchase.credits_amount

    await db.commit()
    logger.info("Credited %d credits to user %s (purchase %s)", purchase.credits_amount, user.id, purchase.id)
    return True
