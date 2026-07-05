from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

CREDIT_PACKAGES = {
    "starter": {"name": "Starter", "credits": 10, "price_brl": 1990},
    "popular": {"name": "Popular", "credits": 30, "price_brl": 4990},
    "pro": {"name": "Pro", "credits": 100, "price_brl": 12990},
}


class PackageResponse(BaseModel):
    id: str = Field(..., description="Package identifier")
    name: str = Field(..., description="Package display name")
    credits: int = Field(..., description="Number of credits included")
    price_brl: int = Field(..., description="Price in BRL cents")
    price_display: str = Field(..., description="Formatted price string")
    bonus_percent: int = Field(default=0, description="Active promotional bonus percent (0 = none)")
    bonus_credits: int = Field(default=0, description="Extra credits granted on purchase")


class CheckoutRequest(BaseModel):
    package: str = Field(..., description="Package ID to purchase")
    provider: str = Field(default="mercadopago", description="Payment provider: mercadopago | stripe")


class CheckoutResponse(BaseModel):
    checkout_url: str = Field(..., description="URL to complete payment")
    purchase_id: UUID = Field(..., description="Internal purchase ID")


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
