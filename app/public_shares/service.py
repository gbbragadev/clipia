from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.service import append_server_event
from app.config import settings
from app.db.models import Job, PublicShareVisit, PublicVideoShare, User
from app.services.acquisition_rewards import claim_social_share_reward

_TOKEN_CONTEXT = b"clipia-public-share:v1:"
_TOKEN_BYTES = 32
DELIVERED_JOB_STATUSES = ("editable", "completed")
_BOT_USER_AGENT = re.compile(
    r"bot|crawler|spider|slurp|headless|curl|wget|python-requests|python-httpx|facebookexternalhit|preview",
    re.IGNORECASE,
)


class PublicShareNotFound(Exception):
    """The public capability is absent, inactive, or not owned by the caller."""


@dataclass(frozen=True)
class PublicShareRecord:
    share: PublicVideoShare
    job: Job
    token: str


def _share_token(share_id: uuid.UUID) -> str:
    signature = hmac.new(
        settings.JWT_SECRET.encode("utf-8"),
        _TOKEN_CONTEXT + share_id.bytes,
        hashlib.sha256,
    ).digest()[:16]
    return base64.urlsafe_b64encode(share_id.bytes + signature).rstrip(b"=").decode("ascii")


def _share_id_from_token(token: str) -> uuid.UUID | None:
    if len(token) != 43 or not re.fullmatch(r"[A-Za-z0-9_-]+", token):
        return None
    try:
        decoded = base64.urlsafe_b64decode(token + "=")
    except (ValueError, TypeError):
        return None
    if len(decoded) != _TOKEN_BYTES:
        return None
    share_id = uuid.UUID(bytes=decoded[:16])
    expected = hmac.new(
        settings.JWT_SECRET.encode("utf-8"),
        _TOKEN_CONTEXT + share_id.bytes,
        hashlib.sha256,
    ).digest()[:16]
    if not hmac.compare_digest(decoded[16:], expected):
        return None
    return share_id


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _new_share_id() -> uuid.UUID:
    return uuid.UUID(bytes=secrets.token_bytes(16), version=4)


def _as_uuid(value: str | uuid.UUID) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise PublicShareNotFound from exc


def classify_user_agent(user_agent: str | None) -> str:
    if not user_agent:
        return "unknown"
    if _BOT_USER_AGENT.search(user_agent):
        return "bot"
    if re.search(r"mozilla|chrome|safari|firefox|edge|opera", user_agent, re.IGNORECASE):
        return "browser"
    return "unknown"


def resolve_public_video_path(job_id: uuid.UUID) -> Path:
    output_dir = (Path(settings.STORAGE_DIR) / "output").resolve()
    candidate = output_dir / f"{job_id}.mp4"
    resolved = candidate.resolve()
    if resolved.parent != output_dir or not resolved.is_file():
        raise PublicShareNotFound
    return resolved


async def create_public_share(db: AsyncSession, owner: User, job_id: str | uuid.UUID) -> PublicShareRecord:
    owned_job = await db.scalar(
        select(Job)
        .where(
            Job.id == _as_uuid(job_id),
            Job.user_id == owner.id,
            Job.status.in_(DELIVERED_JOB_STATUSES),
            Job.completed_at.is_not(None),
            Job.video_url.is_not(None),
        )
        .with_for_update()
    )
    if owned_job is None:
        raise PublicShareNotFound

    share = await db.scalar(
        select(PublicVideoShare).where(
            PublicVideoShare.job_id == owned_job.id,
            PublicVideoShare.active.is_(True),
        )
    )
    if share is not None:
        token = _share_token(share.id)
        if not hmac.compare_digest(share.token_hash, _token_hash(token)):
            raise RuntimeError("public share token key no longer matches persisted hash")
        return PublicShareRecord(share=share, job=owned_job, token=token)

    now = datetime.now(timezone.utc)
    share_id = _new_share_id()
    token = _share_token(share_id)
    share = PublicVideoShare(
        id=share_id,
        job_id=owned_job.id,
        owner_id=owner.id,
        token_hash=_token_hash(token),
        active=True,
    )
    db.add(share)
    try:
        await db.flush()
        await append_server_event(
            db,
            event_name="share_page_published",
            idempotency_key=str(share.id),
            occurred_at=now,
            properties={"share_id": str(share.id), "job_id": str(owned_job.id)},
            user=owner,
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return PublicShareRecord(share=share, job=owned_job, token=token)


async def revoke_public_share(db: AsyncSession, owner: User, job_id: str | uuid.UUID) -> None:
    row = (
        await db.execute(
            select(PublicVideoShare)
            .join(Job, Job.id == PublicVideoShare.job_id)
            .where(
                Job.id == _as_uuid(job_id),
                Job.user_id == owner.id,
                PublicVideoShare.active.is_(True),
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        raise PublicShareNotFound
    row.active = False
    row.revoked_at = datetime.now(timezone.utc)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise


async def get_active_public_share(
    db: AsyncSession,
    token: str,
    *,
    lock: bool = False,
) -> PublicShareRecord:
    share_id = _share_id_from_token(token)
    if share_id is None:
        raise PublicShareNotFound
    statement = (
        select(PublicVideoShare, Job)
        .join(Job, Job.id == PublicVideoShare.job_id)
        .where(
            PublicVideoShare.id == share_id,
            PublicVideoShare.token_hash == _token_hash(token),
            PublicVideoShare.active.is_(True),
            Job.status.in_(DELIVERED_JOB_STATUSES),
            Job.completed_at.is_not(None),
            Job.video_url.is_not(None),
        )
    )
    if lock:
        statement = statement.with_for_update()
    row = (await db.execute(statement)).one_or_none()
    if row is None:
        raise PublicShareNotFound
    share, job = row
    return PublicShareRecord(share=share, job=job, token=token)


async def _insert_qualified_visit(db: AsyncSession, visit: PublicShareVisit) -> bool:
    values = {
        "id": visit.id,
        "share_id": visit.share_id,
        "anonymous_session_id": visit.anonymous_session_id,
        "user_agent_classification": visit.user_agent_classification,
        "visited_at": visit.visited_at,
    }
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        statement = postgresql_insert(PublicShareVisit).values(**values)
    elif dialect == "sqlite":
        statement = sqlite_insert(PublicShareVisit).values(**values)
    else:  # pragma: no cover - supported deployments/tests are PostgreSQL/SQLite
        raise RuntimeError(f"Unsupported public share database dialect: {dialect}")
    statement = statement.on_conflict_do_nothing(
        index_elements=[PublicShareVisit.share_id, PublicShareVisit.anonymous_session_id]
    ).returning(PublicShareVisit.id)
    return (await db.execute(statement)).scalar_one_or_none() is not None


async def record_qualified_view(
    db: AsyncSession,
    *,
    token: str,
    anonymous_session_id: uuid.UUID,
    dwell_ms: int,
    page_visible: bool,
    user_agent: str | None,
    viewer_user_ids: frozenset[uuid.UUID] | set[uuid.UUID],
) -> tuple[bool, bool]:
    record = await get_active_public_share(db, token, lock=True)
    user_agent_classification = classify_user_agent(user_agent)
    if (
        dwell_ms < 5000
        or not page_visible
        or record.share.owner_id in viewer_user_ids
        or user_agent_classification != "browser"
    ):
        return False, False

    now = datetime.now(timezone.utc)
    visit = PublicShareVisit(
        id=uuid.uuid4(),
        share_id=record.share.id,
        anonymous_session_id=anonymous_session_id,
        user_agent_classification=user_agent_classification,
        visited_at=now,
    )
    try:
        if not await _insert_qualified_visit(db, visit):
            await db.commit()
            return False, False
        await append_server_event(
            db,
            event_name="share_page_visited",
            idempotency_key=str(visit.id),
            occurred_at=now,
            properties={"share_id": str(record.share.id), "job_id": str(record.job.id)},
            user=None,
            anonymous_session_id=anonymous_session_id,
        )
        owner = await db.get(User, record.share.owner_id)
        if owner is None:
            raise PublicShareNotFound
        credits = await claim_social_share_reward(db, owner, record.job, now)
        rewarded = credits > 0
        if rewarded:
            await append_server_event(
                db,
                event_name="social_share_rewarded",
                idempotency_key=str(owner.id),
                occurred_at=now,
                properties={
                    "share_id": str(record.share.id),
                    "job_id": str(record.job.id),
                    "credits": credits,
                },
                user=owner,
            )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return True, rewarded
