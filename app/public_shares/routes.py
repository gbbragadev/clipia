from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import FileResponse
from slowapi import Limiter
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.service import decode_access_token_claims
from app.auth.session import AUTH_COOKIE_NAME
from app.config import settings
from app.db.engine import get_db
from app.db.models import User
from app.errors import not_found_error
from app.public_shares.schemas import (
    PublicShareCreated,
    PublicShareMetadata,
    QualifiedViewRequest,
    QualifiedViewResponse,
)
from app.public_shares.service import (
    PublicShareNotFound,
    create_public_share,
    get_active_public_share,
    record_qualified_view,
    resolve_public_video_path,
    revoke_public_share,
)
from app.utils.ratelimit import client_ip

router = APIRouter(tags=["public-shares"])
limiter = Limiter(key_func=client_ip)


def _viewer_user_ids(request: Request) -> frozenset[uuid.UUID]:
    viewer_ids: set[uuid.UUID] = set()
    authorization = request.headers.get("Authorization")
    if authorization:
        scheme, _, candidate = authorization.partition(" ")
        if scheme.lower() == "bearer" and candidate:
            claims = decode_access_token_claims(candidate)
            if claims:
                viewer_ids.add(uuid.UUID(str(claims["sub"])))
    cookie_token = request.cookies.get(AUTH_COOKIE_NAME)
    cookie_claims = decode_access_token_claims(cookie_token) if cookie_token else None
    if cookie_claims:
        viewer_ids.add(uuid.UUID(str(cookie_claims["sub"])))
    return frozenset(viewer_ids)


@router.post(
    "/videos/{job_id}/public-share",
    response_model=PublicShareCreated,
    responses={404: {"description": "Not found"}},
)
@limiter.limit("30/minute")
async def publish_public_share(
    request: Request,
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PublicShareCreated:
    try:
        record = await create_public_share(db, user, job_id)
    except PublicShareNotFound:
        raise not_found_error() from None
    return PublicShareCreated(
        token=record.token,
        url=f"{settings.FRONTEND_URL.rstrip('/')}/v/{record.token}",
        title=record.job.topic,
        active=record.share.active,
    )


@router.delete(
    "/videos/{job_id}/public-share",
    status_code=204,
    responses={404: {"description": "Not found"}},
)
@limiter.limit("30/minute")
async def unpublish_public_share(
    request: Request,
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        await revoke_public_share(db, user, job_id)
    except PublicShareNotFound:
        raise not_found_error() from None
    return Response(status_code=204)


@router.get(
    "/public-shares/{token}",
    response_model=PublicShareMetadata,
    responses={404: {"description": "Not found"}},
)
@limiter.limit("120/minute")
async def get_public_share_metadata(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_db),
) -> PublicShareMetadata:
    try:
        record = await get_active_public_share(db, token)
    except PublicShareNotFound:
        raise not_found_error() from None
    return PublicShareMetadata(
        title=record.job.topic,
        video_url=str(request.url_for("stream_public_share_video", token=token)),
        active=record.share.active,
    )


@router.get(
    "/public-shares/{token}/video",
    name="stream_public_share_video",
    responses={200: {"description": "Video stream"}, 404: {"description": "Not found"}},
)
@limiter.limit("120/minute")
async def stream_public_share_video(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    try:
        record = await get_active_public_share(db, token)
        path = resolve_public_video_path(record.job.id)
    except PublicShareNotFound:
        raise not_found_error() from None
    return FileResponse(str(path), media_type="video/mp4")


@router.post(
    "/public-shares/{token}/qualified-view",
    response_model=QualifiedViewResponse,
    responses={404: {"description": "Not found"}},
)
@limiter.limit("60/minute")
async def qualify_public_share_view(
    request: Request,
    token: str,
    body: QualifiedViewRequest,
    db: AsyncSession = Depends(get_db),
) -> QualifiedViewResponse:
    try:
        qualified, rewarded = await record_qualified_view(
            db,
            token=token,
            anonymous_session_id=body.anonymous_session_id,
            dwell_ms=body.dwell_ms,
            page_visible=body.page_visible,
            user_agent=request.headers.get("User-Agent"),
            viewer_user_ids=_viewer_user_ids(request),
        )
    except PublicShareNotFound:
        raise not_found_error() from None
    return QualifiedViewResponse(qualified=qualified, rewarded=rewarded)
