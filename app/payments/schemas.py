from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.credits import CheckoutPackageKey, PublicPackageIntent

CREDIT_PACKAGES = {
    "starter": {"name": "Starter", "credits": 10, "price_brl": 1990},
    "popular": {"name": "Popular", "credits": 30, "price_brl": 4990},
    "pro": {"name": "Profissional", "credits": 100, "price_brl": 12990},
}


class PackageEquivalences(BaseModel):
    standard_voice: int
    dialogue: int
    script_refinement: int
    ai_image: int
    ai_video: int


class PackageResponse(BaseModel):
    id: PublicPackageIntent = Field(..., description="Public package identifier")
    name: str = Field(..., description="Package display name")
    credits: int = Field(..., description="Number of credits included")
    base_credits: int = Field(..., description="Base credits before the frozen purchase bonus")
    price_brl: int = Field(..., description="Price in BRL cents")
    price_display: str = Field(..., description="Formatted price string")
    bonus_percent: int = Field(default=0, description="Active promotional bonus percent (0 = none)")
    bonus_credits: int = Field(default=0, description="Extra credits granted on purchase")
    total_credits: int = Field(..., description="Base plus bonus credits granted by this package")
    selected_package: PublicPackageIntent = Field(..., description="Public package intent used by registration")
    equivalences: PackageEquivalences = Field(..., description="Whole operations covered by total credits")


class CheckoutRequest(BaseModel):
    package: CheckoutPackageKey = Field(..., description="Package ID to purchase")
    provider: Literal["mercadopago", "stripe"] = Field(
        default="mercadopago", description="Payment provider: mercadopago | stripe"
    )


class CheckoutResponse(BaseModel):
    checkout_url: str = Field(..., description="URL to complete payment")
    purchase_id: UUID = Field(..., description="Internal purchase ID")


class CheckoutStatusResponse(BaseModel):
    purchase_id: UUID = Field(..., description="Internal purchase ID")
    dispatch_id: UUID = Field(..., description="Durable checkout dispatch ID")
    state: Literal["pending", "ready", "failed", "cancelled"] = Field(..., description="Checkout dispatch state")
    checkout_url: str | None = Field(default=None, description="Safe provider URL when ready")


class PurchaseHistoryItem(BaseModel):
    id: UUID = Field(..., description="Purchase ID")
    package_name: str = Field(..., description="Package name")
    credits_amount: int = Field(..., description="Credits amount")
    price_brl: int = Field(..., description="Price in BRL cents")
    status: str = Field(..., description="Payment status")
    created_at: datetime = Field(..., description="Creation timestamp")
    paid_at: datetime | None = Field(default=None, description="Payment timestamp")


class PurchaseHistoryResponse(BaseModel):
    purchases: list[PurchaseHistoryItem] = Field(..., description="List of past purchases")
