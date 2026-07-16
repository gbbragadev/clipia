from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class FunnelCount(BaseModel):
    event_type: str
    count: int


class SourceCount(BaseModel):
    acquisition_source: str
    count: int


class RevenueSummary(BaseModel):
    approved_purchases: int
    gross_amount: float
    currency: str = "BRL"


class MarketingSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_date: date = Field(serialization_alias="from")
    to_date: date = Field(serialization_alias="to")
    funnel: list[FunnelCount]
    sources: list[SourceCount]
    revenue: RevenueSummary


class Attribution(BaseModel):
    acquisition_source: str
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    utm_content: str | None = None
    utm_term: str | None = None


class MarketingConversion(BaseModel):
    event_id: str
    event_type: str
    occurred_at: datetime
    customer_ref: str
    amount: float | None = None
    currency: str | None = None
    attribution: Attribution


class MarketingConversionPage(BaseModel):
    items: list[MarketingConversion]
    next_cursor: str | None = None
