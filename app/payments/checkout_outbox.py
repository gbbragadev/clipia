from __future__ import annotations

import asyncio
import hashlib
import json
import math
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from mercadopago.config import RequestOptions
from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.db.models import CreditPurchase, PaymentCheckoutDispatch, User
from app.payments.schemas import CREDIT_PACKAGES
from app.payments.snapshot import build_snapshot_metadata, freeze_purchase_snapshot
from app.payments.states import canonical_payment_state, payment_state_values

CHECKOUT_LEASE_DURATION = timedelta(minutes=2)
MAX_RETRY_DELAY_SECONDS = 60 * 60

ProviderCall = Callable[["ClaimedCheckout"], Awaitable["ProviderCheckout"]]


@dataclass(frozen=True)
class CheckoutOutcome:
    purchase_id: uuid.UUID
    dispatch_id: uuid.UUID
    state: str
    checkout_url: str | None = None
    error_code: str | None = None
    error_detail: str | None = None


@dataclass(frozen=True)
class ClaimedCheckout:
    dispatch_id: uuid.UUID
    purchase_id: uuid.UUID
    provider: str
    publisher_token: uuid.UUID
    publisher_lease_until: datetime
    provider_idempotency_key: str
    request_payload: str
    request_payload_hash: str
    attempt_count: int


@dataclass(frozen=True)
class ProviderCheckout:
    checkout_id: str
    checkout_url: str
    expires_at: datetime | None = None


class CheckoutIdempotencyConflict(Exception):
    """A client key was replayed for a different provider/package request."""


class CheckoutPending(Exception):
    def __init__(self, outcome: CheckoutOutcome):
        super().__init__("checkout dispatch is pending")
        self.outcome = outcome


class CheckoutFailed(ValueError):
    def __init__(self, outcome: CheckoutOutcome, *, detail: str = "checkout dispatch failed"):
        super().__init__(detail)
        self.outcome = outcome


class _PermanentProviderError(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


class _TransientProviderError(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _payload_hash(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalize_request_key(user_id: uuid.UUID, request_key: str | None) -> str | None:
    if request_key is None:
        return None
    normalized = str(request_key).strip()
    if not normalized or len(normalized) > 200 or any(ord(char) < 32 for char in normalized):
        raise ValueError("Invalid idempotency key")
    return _digest(f"{user_id}\0{normalized}")


def _request_fingerprint(provider: str, package_key: str) -> str:
    return _digest(_canonical_json({"package": package_key, "provider": provider}))


def _frozen_payload_is_valid(payload: str, expected_hash: str) -> bool:
    if _payload_hash(payload) != expected_hash:
        return False
    try:
        decoded = json.loads(payload)
    except (TypeError, ValueError):
        return False
    return isinstance(decoded, dict) and _canonical_json(decoded) == payload


def _build_provider_payload(purchase: CreditPurchase, package: dict[str, Any]) -> str:
    metadata = build_snapshot_metadata(purchase)
    if purchase.provider == "stripe":
        payload = {
            "cancel_url": f"{settings.FRONTEND_URL}/dashboard/credits?status=failure",
            "client_reference_id": str(purchase.id),
            "line_items": [
                {
                    "price_data": {
                        "currency": "brl",
                        "product_data": {"name": f"ClipIA - {package['name']} ({package['credits']} creditos)"},
                        "unit_amount": package["price_brl"],
                    },
                    "quantity": 1,
                }
            ],
            "metadata": metadata,
            "mode": "payment",
            "payment_intent_data": {"metadata": metadata},
            "success_url": f"{settings.FRONTEND_URL}/dashboard/credits?status=success",
        }
    else:
        payload = {
            "external_reference": str(purchase.id),
            "items": [
                {
                    "currency_id": "BRL",
                    "id": purchase.package_name,
                    "quantity": 1,
                    "title": f"ClipIA - {package['name']} ({package['credits']} creditos)",
                    "unit_price": package["price_brl"] / 100,
                }
            ],
            "metadata": metadata,
        }
        if settings.FRONTEND_URL.startswith("https://"):
            payload["auto_return"] = "approved"
            payload["back_urls"] = {
                "failure": f"{settings.FRONTEND_URL}/dashboard/credits?status=failure",
                "pending": f"{settings.FRONTEND_URL}/dashboard/credits?status=pending",
                "success": f"{settings.FRONTEND_URL}/dashboard/credits?status=success",
            }
        if settings.BACKEND_URL and settings.BACKEND_URL.startswith("https://"):
            payload["notification_url"] = f"{settings.BACKEND_URL}/api/v1/webhooks/mercadopago"
    return _canonical_json(payload)


def _outcome(dispatch: PaymentCheckoutDispatch) -> CheckoutOutcome:
    return CheckoutOutcome(
        purchase_id=dispatch.purchase_id,
        dispatch_id=dispatch.id,
        state=dispatch.state,
        checkout_url=dispatch.checkout_url if dispatch.state == "ready" else None,
        error_code=dispatch.error_code,
        error_detail=dispatch.error_detail,
    )


async def _load_request_key_dispatch(
    db: AsyncSession,
    scoped_request_key: str,
) -> PaymentCheckoutDispatch | None:
    return await db.scalar(
        select(PaymentCheckoutDispatch).where(PaymentCheckoutDispatch.request_key == scoped_request_key)
    )


async def _resume_existing(
    db: AsyncSession,
    dispatch: PaymentCheckoutDispatch,
    fingerprint: str,
    *,
    attempt_inline: bool,
    provider_call: ProviderCall | None,
) -> CheckoutOutcome:
    if dispatch.request_fingerprint != fingerprint:
        await db.rollback()
        raise CheckoutIdempotencyConflict("idempotency key reused with a different request")
    existing = _outcome(dispatch)
    existing_state = dispatch.state
    existing_id = dispatch.id
    await db.rollback()
    if existing_state != "pending" or not attempt_inline:
        return existing
    attempted = await dispatch_checkout(db, existing_id, provider_call=provider_call)
    return attempted or existing


async def create_or_resume_checkout(
    user: User,
    package_key: str,
    provider: str,
    db: AsyncSession,
    request_key: str | None = None,
    *,
    attempt_inline: bool = True,
    provider_call: ProviderCall | None = None,
) -> CheckoutOutcome:
    """Commit purchase + frozen request before any provider call, then optionally dispatch."""
    normalized_provider = str(provider).strip().lower()
    normalized_package = str(package_key).strip()
    user_id = user.id
    if normalized_provider not in {"mercadopago", "stripe"}:
        raise ValueError("Invalid payment provider")

    scoped_request_key = _normalize_request_key(user_id, request_key)
    fingerprint = _request_fingerprint(normalized_provider, normalized_package)
    if scoped_request_key is not None:
        existing = await _load_request_key_dispatch(db, scoped_request_key)
        if existing is not None:
            return await _resume_existing(
                db,
                existing,
                fingerprint,
                attempt_inline=attempt_inline,
                provider_call=provider_call,
            )
        await db.rollback()

    package = CREDIT_PACKAGES.get(normalized_package)
    if package is None:
        raise ValueError("Invalid credit package")

    purchase = CreditPurchase(
        id=uuid.uuid4(),
        user_id=user_id,
        package_name=normalized_package,
        credits_amount=package["credits"],
        bonus_credits=package["credits"] * settings.PURCHASE_BONUS_PERCENT // 100,
        price_brl=package["price_brl"],
        provider=normalized_provider,
        mp_preference_id=None,
        currency="BRL",
        **payment_state_values("pending"),
    )
    freeze_purchase_snapshot(purchase)
    request_payload = _build_provider_payload(purchase, package)
    now = _utcnow()
    dispatch = PaymentCheckoutDispatch(
        id=uuid.uuid4(),
        purchase_id=purchase.id,
        user_id=user_id,
        provider=normalized_provider,
        provider_idempotency_key=f"clipia:checkout:{normalized_provider}:{purchase.id}",
        request_key=scoped_request_key,
        request_fingerprint=fingerprint if scoped_request_key is not None else None,
        request_payload=request_payload,
        request_payload_hash=_payload_hash(request_payload),
        state="pending",
        next_attempt_at=now,
    )
    db.add_all([purchase, dispatch])
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        if scoped_request_key is None:
            raise
        existing = await _load_request_key_dispatch(db, scoped_request_key)
        if existing is None:
            await db.rollback()
            raise
        return await _resume_existing(
            db,
            existing,
            fingerprint,
            attempt_inline=attempt_inline,
            provider_call=provider_call,
        )
    except Exception:
        await db.rollback()
        raise

    pending = _outcome(dispatch)
    if not attempt_inline:
        return pending
    try:
        attempted = await dispatch_checkout(db, dispatch.id, provider_call=provider_call)
    except Exception:
        await db.rollback()
        return pending
    return attempted or pending


async def _fail_locked_dispatch(
    purchase: CreditPurchase,
    dispatch: PaymentCheckoutDispatch,
    *,
    state: str,
    code: str,
    detail: str,
    now: datetime,
) -> None:
    try:
        purchase_state = canonical_payment_state(purchase.status, purchase.payment_state)
    except ValueError:
        purchase_state = "pending"
    if state == "failed" and purchase_state not in {"paid", "refunded"}:
        for field, value in payment_state_values("void").items():
            setattr(purchase, field, value)
    dispatch.state = state
    dispatch.next_attempt_at = None
    dispatch.publisher_token = None
    dispatch.publisher_lease_until = None
    dispatch.provider_checkout_id = None
    dispatch.checkout_url = None
    dispatch.checkout_expires_at = None
    dispatch.error_code = code
    dispatch.error_detail = detail[:255]
    dispatch.failed_at = now
    dispatch.ready_at = None


async def claim_checkout_dispatch(
    db: AsyncSession,
    dispatch_id: uuid.UUID | None = None,
    *,
    now: datetime | None = None,
    lease_duration: timedelta = CHECKOUT_LEASE_DURATION,
) -> ClaimedCheckout | None:
    """Claim one due row with a committed PostgreSQL SKIP LOCKED lease."""
    claimed_at = now or _utcnow()
    statement = (
        select(PaymentCheckoutDispatch)
        .where(
            PaymentCheckoutDispatch.state == "pending",
            PaymentCheckoutDispatch.next_attempt_at <= claimed_at,
            or_(
                PaymentCheckoutDispatch.publisher_lease_until.is_(None),
                PaymentCheckoutDispatch.publisher_lease_until <= claimed_at,
            ),
        )
        .order_by(PaymentCheckoutDispatch.next_attempt_at, PaymentCheckoutDispatch.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
        .execution_options(populate_existing=True)
    )
    if dispatch_id is not None:
        statement = statement.where(PaymentCheckoutDispatch.id == dispatch_id)
    dispatch = (await db.execute(statement)).scalar_one_or_none()
    if dispatch is None:
        await db.rollback()
        return None

    purchase = (
        await db.execute(
            select(CreditPurchase)
            .where(CreditPurchase.id == dispatch.purchase_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if purchase is None:
        await db.rollback()
        return None

    try:
        purchase_state = canonical_payment_state(purchase.status, purchase.payment_state)
    except ValueError:
        purchase_state = "void"
    if purchase_state == "void":
        await _fail_locked_dispatch(
            purchase,
            dispatch,
            state="cancelled",
            code="purchase_terminal",
            detail="purchase is terminal before checkout dispatch",
            now=claimed_at,
        )
        await db.commit()
        return None
    if not _frozen_payload_is_valid(dispatch.request_payload, dispatch.request_payload_hash):
        await _fail_locked_dispatch(
            purchase,
            dispatch,
            state="failed",
            code="payload_corrupt",
            detail="frozen provider request failed integrity validation",
            now=claimed_at,
        )
        await db.commit()
        return None

    token = uuid.uuid4()
    lease_until = claimed_at + lease_duration
    dispatch.attempt_count += 1
    dispatch.last_attempt_at = claimed_at
    dispatch.publisher_token = token
    dispatch.publisher_lease_until = lease_until
    dispatch.error_code = None
    dispatch.error_detail = None
    await db.commit()
    return ClaimedCheckout(
        dispatch_id=dispatch.id,
        purchase_id=dispatch.purchase_id,
        provider=dispatch.provider,
        publisher_token=token,
        publisher_lease_until=lease_until,
        provider_idempotency_key=dispatch.provider_idempotency_key,
        request_payload=dispatch.request_payload,
        request_payload_hash=dispatch.request_payload_hash,
        attempt_count=dispatch.attempt_count,
    )


def _provider_status(exc: Exception) -> int | None:
    for name in ("http_status", "status", "status_code"):
        value = getattr(exc, name, None)
        if isinstance(value, int):
            return value
    return None


def _classify_provider_exception(exc: Exception) -> None:
    status = _provider_status(exc)
    if status == 429:
        raise _TransientProviderError("rate_limited", "provider rate limited checkout creation") from exc
    if status is not None and status >= 500:
        raise _TransientProviderError("provider_unavailable", "provider returned a server error") from exc
    if status is not None and 400 <= status < 500:
        raise _PermanentProviderError("provider_rejected", "provider rejected the frozen request") from exc
    if isinstance(exc, (TimeoutError, ConnectionError, asyncio.TimeoutError)):
        raise _TransientProviderError("provider_unavailable", "provider outcome is ambiguous") from exc
    raise exc


def _parse_expiry(value: object) -> datetime | None:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
    return None


async def _call_provider(claim: ClaimedCheckout) -> ProviderCheckout:
    """Call the provider once; the outbox, not an SDK, owns retry accounting."""
    from app.payments import service as payment_service

    payload = json.loads(claim.request_payload)
    if claim.provider == "mercadopago":
        request_options = RequestOptions(
            access_token=settings.MP_ACCESS_TOKEN,
            custom_headers={"x-idempotency-key": claim.provider_idempotency_key},
            max_retries=0,
        )
        try:
            sdk = payment_service._get_sdk()
            result = await asyncio.to_thread(sdk.preference().create, payload, request_options)
        except Exception as exc:  # provider exceptions require fail-safe classification
            _classify_provider_exception(exc)
        status = result.get("status") if isinstance(result, dict) else None
        if status == 429 or (isinstance(status, int) and status >= 500):
            code = "rate_limited" if status == 429 else "provider_unavailable"
            raise _TransientProviderError(code, "provider outcome is ambiguous")
        if status != 201 or not isinstance(result.get("response"), dict):
            raise _PermanentProviderError("provider_rejected", "provider rejected the frozen request")
        response = result["response"]
        checkout_id = str(response.get("id") or "").strip()
        checkout_url = str(response.get("init_point") or response.get("sandbox_init_point") or "").strip()
        if not checkout_id or not checkout_url:
            raise _PermanentProviderError(
                "invalid_response",
                "Provider response missing checkout identity or URL",
            )
        return ProviderCheckout(
            checkout_id=checkout_id,
            checkout_url=checkout_url,
            expires_at=_parse_expiry(response.get("date_of_expiration")),
        )

    if not settings.STRIPE_SECRET_KEY:
        raise _PermanentProviderError("config_invalid", "Stripe is not configured")
    payment_service._init_stripe()
    try:
        session = await asyncio.to_thread(
            lambda: payment_service.stripe.checkout.Session.create(
                **payload,
                idempotency_key=claim.provider_idempotency_key,
            )
        )
    except Exception as exc:  # provider exceptions require fail-safe classification
        _classify_provider_exception(exc)
    checkout_id = str(getattr(session, "id", "") or "").strip()
    checkout_url = str(getattr(session, "url", "") or "").strip()
    if not checkout_id or not checkout_url:
        raise _PermanentProviderError(
            "invalid_response",
            "Provider response missing checkout identity or URL",
        )
    return ProviderCheckout(
        checkout_id=checkout_id,
        checkout_url=checkout_url,
        expires_at=_parse_expiry(getattr(session, "expires_at", None)),
    )


def _retry_delay(attempt_count: int) -> timedelta:
    seconds = min(MAX_RETRY_DELAY_SECONDS, max(2, 2 ** min(max(attempt_count, 1), 20)))
    return timedelta(seconds=seconds)


async def _schedule_retry(
    db: AsyncSession,
    claim: ClaimedCheckout,
    *,
    code: str,
    detail: str,
    now: datetime | None = None,
) -> bool:
    retry_at = (now or _utcnow()) + _retry_delay(claim.attempt_count)
    result = await db.execute(
        update(PaymentCheckoutDispatch)
        .where(
            PaymentCheckoutDispatch.id == claim.dispatch_id,
            PaymentCheckoutDispatch.state == "pending",
            PaymentCheckoutDispatch.publisher_token == claim.publisher_token,
        )
        .values(
            next_attempt_at=retry_at,
            publisher_token=None,
            publisher_lease_until=None,
            error_code=code,
            error_detail=detail[:255],
        )
    )
    await db.commit()
    return result.rowcount == 1


async def _terminalize_claim(
    db: AsyncSession,
    claim: ClaimedCheckout,
    *,
    state: str,
    code: str,
    detail: str,
) -> bool:
    now = _utcnow()
    dispatch = (
        await db.execute(
            select(PaymentCheckoutDispatch)
            .where(
                PaymentCheckoutDispatch.id == claim.dispatch_id,
                PaymentCheckoutDispatch.state == "pending",
                PaymentCheckoutDispatch.publisher_token == claim.publisher_token,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if dispatch is None:
        await db.rollback()
        return False
    purchase = (
        await db.execute(select(CreditPurchase).where(CreditPurchase.id == dispatch.purchase_id).with_for_update())
    ).scalar_one()
    await _fail_locked_dispatch(
        purchase,
        dispatch,
        state=state,
        code=code,
        detail=detail,
        now=now,
    )
    await db.commit()
    return True


async def finalize_checkout_dispatch(
    db: AsyncSession,
    claim: ClaimedCheckout,
    provider_checkout: ProviderCheckout,
) -> bool:
    """Atomically bind purchase + ready dispatch, guarded by the publisher token."""
    from app.payments import service as payment_service

    if not payment_service._valid_checkout_response(
        claim.provider,
        provider_checkout.checkout_id,
        provider_checkout.checkout_url,
    ):
        await _terminalize_claim(
            db,
            claim,
            state="failed",
            code="invalid_response",
            detail="Provider response has invalid checkout identity or URL",
        )
        return False

    now = _utcnow()
    dispatch = (
        await db.execute(
            select(PaymentCheckoutDispatch)
            .where(PaymentCheckoutDispatch.id == claim.dispatch_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if (
        dispatch is None
        or dispatch.state != "pending"
        or dispatch.publisher_token != claim.publisher_token
        or dispatch.publisher_lease_until is None
    ):
        await db.rollback()
        return False
    lease_until = dispatch.publisher_lease_until
    if lease_until.tzinfo is None:
        lease_until = lease_until.replace(tzinfo=timezone.utc)
    if lease_until <= now:
        await db.rollback()
        return False

    purchase = (
        await db.execute(
            select(CreditPurchase)
            .where(CreditPurchase.id == dispatch.purchase_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    try:
        purchase_state = canonical_payment_state(purchase.status, purchase.payment_state)
    except ValueError:
        purchase_state = "void"
    if purchase_state == "void":
        await _fail_locked_dispatch(
            purchase,
            dispatch,
            state="cancelled",
            code="purchase_terminal",
            detail="purchase became terminal before checkout binding",
            now=now,
        )
        await db.commit()
        return False

    stored_identity = (
        str(purchase.mp_preference_id).strip() if purchase.mp_preference_id not in (None, "", "pending") else None
    )
    collision = await db.scalar(
        select(CreditPurchase.id).where(
            CreditPurchase.provider == claim.provider,
            CreditPurchase.mp_preference_id == provider_checkout.checkout_id,
            CreditPurchase.id != purchase.id,
        )
    )
    dispatch_collision = await db.scalar(
        select(PaymentCheckoutDispatch.id).where(
            PaymentCheckoutDispatch.provider == claim.provider,
            PaymentCheckoutDispatch.provider_checkout_id == provider_checkout.checkout_id,
            PaymentCheckoutDispatch.id != dispatch.id,
        )
    )
    if (
        (stored_identity is not None and stored_identity != provider_checkout.checkout_id)
        or collision
        or dispatch_collision
    ):
        await _fail_locked_dispatch(
            purchase,
            dispatch,
            state="failed",
            code="identity_collision",
            detail="provider checkout identity conflicts with durable authority",
            now=now,
        )
        await db.commit()
        return False

    if stored_identity is None:
        purchase.mp_preference_id = provider_checkout.checkout_id
    dispatch.state = "ready"
    dispatch.provider_checkout_id = provider_checkout.checkout_id
    dispatch.checkout_url = provider_checkout.checkout_url
    dispatch.checkout_expires_at = provider_checkout.expires_at
    dispatch.ready_at = now
    dispatch.failed_at = None
    dispatch.next_attempt_at = None
    dispatch.publisher_token = None
    dispatch.publisher_lease_until = None
    dispatch.error_code = None
    dispatch.error_detail = None
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        await _terminalize_claim(
            db,
            claim,
            state="failed",
            code="identity_collision",
            detail="provider checkout identity conflicts with durable authority",
        )
        return False
    except Exception:
        await db.rollback()
        try:
            await _schedule_retry(
                db,
                claim,
                code="binding_failed",
                detail="provider accepted but durable binding did not commit",
            )
        except Exception:
            await db.rollback()
        return False
    return True


async def _current_outcome(db: AsyncSession, dispatch_id: uuid.UUID) -> CheckoutOutcome | None:
    dispatch = await db.get(PaymentCheckoutDispatch, dispatch_id, populate_existing=True)
    result = _outcome(dispatch) if dispatch is not None else None
    await db.rollback()
    return result


async def dispatch_checkout(
    db: AsyncSession,
    dispatch_id: uuid.UUID | None = None,
    *,
    provider_call: ProviderCall | None = None,
) -> CheckoutOutcome | None:
    """Claim, call outside a transaction, and finalize/retry with token CAS."""
    try:
        claim = await claim_checkout_dispatch(db, dispatch_id)
    except Exception:
        await db.rollback()
        return await _current_outcome(db, dispatch_id) if dispatch_id is not None else None
    if claim is None:
        return await _current_outcome(db, dispatch_id) if dispatch_id is not None else None

    call = provider_call or _call_provider
    try:
        provider_checkout = await call(claim)
    except _PermanentProviderError as exc:
        await _terminalize_claim(db, claim, state="failed", code=exc.code, detail=exc.detail)
    except _TransientProviderError as exc:
        await _schedule_retry(db, claim, code=exc.code, detail=exc.detail)
    except Exception:
        await _schedule_retry(
            db,
            claim,
            code="provider_unavailable",
            detail="provider outcome is ambiguous",
        )
    else:
        await finalize_checkout_dispatch(db, claim, provider_checkout)
    return await _current_outcome(db, claim.dispatch_id)


async def reconcile_checkout_dispatches(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    limit: int = 25,
    provider_call: ProviderCall | None = None,
) -> dict[str, int]:
    counts = {"ready": 0, "pending": 0, "failed": 0, "cancelled": 0}
    for _ in range(max(0, min(limit, 100))):
        async with session_factory() as db:
            result = await dispatch_checkout(db, provider_call=provider_call)
        if result is None:
            break
        counts[result.state] += 1
    return counts


async def get_checkout_outcome(
    db: AsyncSession,
    *,
    purchase_id: uuid.UUID,
    user_id: uuid.UUID,
) -> CheckoutOutcome | None:
    dispatch = await db.scalar(
        select(PaymentCheckoutDispatch).where(
            PaymentCheckoutDispatch.purchase_id == purchase_id,
            PaymentCheckoutDispatch.user_id == user_id,
        )
    )
    result = _outcome(dispatch) if dispatch is not None else None
    await db.rollback()
    return result
