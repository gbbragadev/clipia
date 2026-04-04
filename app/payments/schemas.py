from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


CREDIT_PACKAGES = {
    "starter": {"name": "Starter", "credits": 5, "price_brl": 1990},
    "popular": {"name": "Popular", "credits": 15, "price_brl": 4990},
    "pro": {"name": "Pro", "credits": 50, "price_brl": 12990},
}


class PackageResponse(BaseModel):
    id: str
    name: str
    credits: int
    price_brl: int  # centavos
    price_display: str  # "R$ 19,90"


class CheckoutRequest(BaseModel):
    package: str  # "starter", "popular", "pro"


class CheckoutResponse(BaseModel):
    checkout_url: str
    purchase_id: UUID


class PurchaseHistoryItem(BaseModel):
    id: UUID
    package_name: str
    credits_amount: int
    price_brl: int
    status: str
    created_at: datetime
    paid_at: datetime | None


class PurchaseHistoryResponse(BaseModel):
    purchases: list[PurchaseHistoryItem]
