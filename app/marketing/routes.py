from __future__ import annotations

import secrets
from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.engine import get_db
from app.marketing.export import build_marketing_conversions, build_marketing_summary
from app.marketing.schemas import MarketingConversionPage, MarketingSummary

router = APIRouter(prefix="/internal/marketing", tags=["internal-marketing"])
_MAX_EXPORT_DAYS = 90


def require_marketing_token(x_marketing_token: str | None = Header(default=None, alias="X-Marketing-Token")) -> None:
    configured = settings.MARKETING_EXPORT_TOKEN
    supplied = x_marketing_token or ""
    if not configured or not secrets.compare_digest(supplied, configured):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid marketing token")


def validate_date_range(from_date: date, to_date: date) -> None:
    if from_date > to_date:
        raise HTTPException(status_code=422, detail="from must not be after to")
    if (to_date - from_date).days > _MAX_EXPORT_DAYS:
        raise HTTPException(status_code=422, detail=f"date range must not exceed {_MAX_EXPORT_DAYS} days")
    if to_date > date.today():
        raise HTTPException(status_code=422, detail="to must not be in the future")


@router.get("/summary", response_model=MarketingSummary, response_model_by_alias=True)
async def marketing_summary(
    from_date: date = Query(alias="from"),
    to_date: date = Query(alias="to"),
    _authorized: None = Depends(require_marketing_token),
    db: AsyncSession = Depends(get_db),
):
    validate_date_range(from_date, to_date)
    return await build_marketing_summary(db, from_date=from_date, to_date=to_date)


@router.get("/conversions", response_model=MarketingConversionPage)
async def marketing_conversions(
    cursor: str | None = Query(default=None, max_length=512),
    limit: int = Query(default=50, ge=1, le=100),
    _authorized: None = Depends(require_marketing_token),
    db: AsyncSession = Depends(get_db),
):
    if not settings.MARKETING_PSEUDONYM_SECRET:
        raise HTTPException(status_code=503, detail="Marketing pseudonymization is not configured")
    try:
        return await build_marketing_conversions(db, cursor=cursor, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
