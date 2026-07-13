from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import ValidationError
from slowapi import Limiter
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.schemas import AnalyticsBatch, AnalyticsIngestResponse
from app.analytics.service import AnalyticsEventConflict, ingest_client_events
from app.auth.dependencies import get_optional_current_user
from app.config import settings
from app.db.engine import get_db
from app.db.models import User
from app.errors import ErrorMessages
from app.utils.ratelimit import client_ip

MAX_ANALYTICS_BODY_BYTES = 65_536
MAX_ANALYTICS_BATCH_EVENTS = 20

router = APIRouter(tags=["analytics"])
limiter = Limiter(key_func=client_ip)


async def _read_limited_body(request: Request) -> bytes:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_ANALYTICS_BODY_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=ErrorMessages.PAYLOAD_TOO_LARGE
                )
        except ValueError:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=ErrorMessages.INVALID_INPUT)

    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_ANALYTICS_BODY_BYTES:
            raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=ErrorMessages.PAYLOAD_TOO_LARGE)
        chunks.append(chunk)
    return b"".join(chunks)


def _parse_batch(raw: bytes) -> AnalyticsBatch:
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=ErrorMessages.INVALID_INPUT
        ) from exc

    if isinstance(payload, dict) and isinstance(payload.get("events"), list):
        if len(payload["events"]) > MAX_ANALYTICS_BATCH_EVENTS:
            raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=ErrorMessages.PAYLOAD_TOO_LARGE)

    try:
        return AnalyticsBatch.model_validate(payload)
    except ValidationError as exc:
        errors = [
            {
                "field": ".".join(str(part) for part in error.get("loc", ())) or "body",
                "message": error.get("msg", ErrorMessages.INVALID_INPUT),
            }
            for error in exc.errors(include_url=False, include_context=False, include_input=False)
        ]
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_analytics_event", "errors": errors},
        ) from exc


@router.post(
    "/analytics/events",
    response_model=AnalyticsIngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest first-party product events",
    responses={
        202: {"description": "Batch accepted or analytics disabled"},
        409: {"description": "event_id reused with a different payload"},
        413: {"description": "Batch or raw body too large"},
        422: {"description": "Unknown or invalid event contract"},
    },
)
@limiter.limit(settings.ANALYTICS_RATE_LIMIT)
async def ingest_analytics_events(
    request: Request,
    user: User | None = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalyticsIngestResponse:
    batch = _parse_batch(await _read_limited_body(request))
    if not settings.ANALYTICS_ENABLED:
        return AnalyticsIngestResponse(accepted=0, duplicates=0, enabled=False)

    try:
        accepted, duplicates = await ingest_client_events(db, batch, user)
    except AnalyticsEventConflict as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "analytics_event_conflict"},
        ) from exc
    return AnalyticsIngestResponse(accepted=accepted, duplicates=duplicates, enabled=True)
