from __future__ import annotations

import asyncio
import hashlib
import json
import math
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import stripe
from mercadopago.config import RequestOptions
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.db.models import CreditPurchase, PaymentCheckoutDispatch, User
from app.payments.schemas import CREDIT_PACKAGES
from app.payments.snapshot import build_snapshot_metadata, freeze_purchase_snapshot
from app.payments.states import canonical_payment_state, payment_state_values

CHECKOUT_LEASE_DURATION = timedelta(minutes=2)
MAX_RETRY_DELAY_SECONDS = 60 * 60
MAX_CHECKOUT_ATTEMPTS = 8
PROVIDER_REQUEST_TIMEOUT_SECONDS = 10.0
STRIPE_REQUEST_TIMEOUT_SECONDS = PROVIDER_REQUEST_TIMEOUT_SECONDS
STRIPE_RETRY_HORIZON = timedelta(hours=23)

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
    created_at: datetime


@dataclass(frozen=True)
class ProviderCheckout:
    checkout_id: str
    checkout_url: str
    expires_at: datetime | None = None


class CheckoutIdempotencyConflict(Exception):
    """A client key was replayed for a different provider/package request."""


class InvalidCheckoutIdempotencyKey(ValueError):
    """The caller supplied an unsafe or unusable checkout idempotency key."""


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


class _ManualProviderError(Exception):
    """Automatic recovery cannot prove a unique provider object safely."""

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
    if not normalized or len(normalized) > 200 or any(ord(char) < 32 or ord(char) == 127 for char in normalized):
        raise InvalidCheckoutIdempotencyKey("Invalid idempotency key")
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
    database_now = await db.scalar(select(func.now()))
    if not isinstance(database_now, datetime):
        await db.rollback()
        raise RuntimeError("database clock is unavailable")
    now = _aware_utc(database_now)
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
    void_purchase: bool = True,
) -> None:
    try:
        purchase_state = canonical_payment_state(purchase.status, purchase.payment_state)
    except ValueError:
        purchase_state = "pending"
    if void_purchase and state == "failed" and purchase_state not in {"paid", "refunded"}:
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
) -> ClaimedCheckout | CheckoutOutcome | None:
    """Claim one due row with a committed PostgreSQL SKIP LOCKED lease."""
    if now is None:
        database_now = await db.scalar(select(func.now()))
        if not isinstance(database_now, datetime):
            await db.rollback()
            raise RuntimeError("database clock is unavailable")
        claimed_at = _aware_utc(database_now)
    else:
        claimed_at = _aware_utc(now)
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
    if purchase_state in {"paid", "refunded", "void"}:
        await _fail_locked_dispatch(
            purchase,
            dispatch,
            state="cancelled",
            code="purchase_terminal",
            detail=f"purchase is {purchase_state} before checkout dispatch",
            now=claimed_at,
        )
        await db.commit()
        return _outcome(dispatch)
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
        return _outcome(dispatch)

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
        created_at=dispatch.created_at,
    )


def _provider_status(exc: Exception) -> int | None:
    for name in ("http_status", "status", "status_code"):
        value = getattr(exc, name, None)
        if isinstance(value, int):
            return value
    return None


def _classify_provider_exception(exc: Exception) -> None:
    status = _provider_status(exc)
    if isinstance(exc, (TimeoutError, ConnectionError, asyncio.TimeoutError)) or status in {408, 409, 424, 425}:
        raise _TransientProviderError("provider_unavailable", "provider outcome is ambiguous") from exc
    if status == 429:
        raise _TransientProviderError("rate_limited", "provider rate limited checkout creation") from exc
    if status is not None and status >= 500:
        raise _TransientProviderError("provider_unavailable", "provider returned a server error") from exc
    if status is not None and 400 <= status < 500:
        raise _PermanentProviderError("provider_rejected", "provider rejected the frozen request") from exc
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


def _aware_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _plain_provider_object(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "to_dict"):
        converted = value.to_dict()
        return dict(converted) if isinstance(converted, dict) else {}
    try:
        return dict(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return dict(vars(value)) if hasattr(value, "__dict__") else {}


def _exact_metadata(actual: object, expected: object) -> bool:
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return False
    return {str(key): str(value) for key, value in actual.items()} == {
        str(key): str(value) for key, value in expected.items()
    }


def _mp_items_match(actual: object, expected: object) -> bool:
    if (
        not isinstance(actual, list)
        or not isinstance(expected, list)
        or len(actual) != 1
        or len(expected) != 1
        or not isinstance(actual[0], dict)
        or not isinstance(expected[0], dict)
    ):
        return False
    actual_item = actual[0]
    expected_item = expected[0]
    for field in ("id", "title", "currency_id"):
        if str(actual_item.get(field) or "") != str(expected_item.get(field) or ""):
            return False
    try:
        actual_quantity = int(actual_item.get("quantity"))
        expected_quantity = int(expected_item.get("quantity"))
        actual_price = Decimal(str(actual_item.get("unit_price")))
        expected_price = Decimal(str(expected_item.get("unit_price")))
    except (InvalidOperation, TypeError, ValueError):
        return False
    return actual_quantity == expected_quantity and actual_price == expected_price


def _mp_request_options(*, idempotency_key: str | None = None) -> RequestOptions:
    headers = {"x-idempotency-key": idempotency_key} if idempotency_key is not None else None
    return RequestOptions(
        access_token=settings.MP_ACCESS_TOKEN,
        connection_timeout=PROVIDER_REQUEST_TIMEOUT_SECONDS,
        custom_headers=headers,
        max_retries=0,
    )


def _mp_status(result: object) -> int | None:
    if not isinstance(result, dict):
        return None
    value = result.get("status")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _raise_for_ambiguous_result(status: int | None, *, action: str) -> None:
    if status == 429:
        raise _TransientProviderError("rate_limited", f"provider rate limited checkout {action}")
    if status in {408, 409, 424, 425} or (status is not None and status >= 500):
        raise _TransientProviderError("provider_unavailable", f"provider checkout {action} is ambiguous")


async def _reconcile_mercadopago_preference(
    preference: object,
    claim: ClaimedCheckout,
    payload: dict[str, Any],
) -> ProviderCheckout:
    expected_reference = str(payload.get("external_reference") or "")
    request_options = _mp_request_options()
    try:
        search_result = await asyncio.to_thread(
            preference.search,  # type: ignore[attr-defined]
            {"external_reference": expected_reference},
            request_options,
        )
    except Exception as exc:
        try:
            _classify_provider_exception(exc)
        except _PermanentProviderError as classified:
            raise _ManualProviderError(
                "provider_unavailable", "provider preference search requires review"
            ) from classified
        raise

    search_status = _mp_status(search_result)
    _raise_for_ambiguous_result(search_status, action="search")
    search_response = search_result.get("response") if isinstance(search_result, dict) else None
    if search_status != 200 or not isinstance(search_response, dict):
        raise _ManualProviderError("provider_unavailable", "provider preference search requires review")
    elements = search_response.get("elements")
    if not isinstance(elements, list):
        raise _ManualProviderError("provider_unavailable", "provider preference search returned malformed results")
    if not elements:
        raise _TransientProviderError("provider_unavailable", "provider preference is not visible yet")
    if len(elements) != 1:
        raise _ManualProviderError("provider_unavailable", "multiple provider preferences require manual review")

    candidate = _plain_provider_object(elements[0])
    preference_id = str(candidate.get("id") or "").strip()
    if not preference_id:
        raise _ManualProviderError("provider_unavailable", "provider preference identity is missing")
    try:
        get_result = await asyncio.to_thread(
            preference.get,  # type: ignore[attr-defined]
            preference_id,
            request_options,
        )
    except Exception as exc:
        try:
            _classify_provider_exception(exc)
        except _PermanentProviderError as classified:
            raise _ManualProviderError(
                "provider_unavailable", "provider preference lookup requires review"
            ) from classified
        raise

    get_status = _mp_status(get_result)
    _raise_for_ambiguous_result(get_status, action="lookup")
    response = get_result.get("response") if isinstance(get_result, dict) else None
    if get_status != 200 or not isinstance(response, dict):
        raise _ManualProviderError("provider_unavailable", "provider preference lookup requires review")

    checkout_id = str(response.get("id") or "").strip()
    checkout_url = str(response.get("init_point") or response.get("sandbox_init_point") or "").strip()
    from app.payments import service as payment_service

    if (
        checkout_id != preference_id
        or str(response.get("external_reference") or "") != expected_reference
        or not _exact_metadata(response.get("metadata"), payload.get("metadata"))
        or not _mp_items_match(response.get("items"), payload.get("items"))
        or not payment_service._valid_checkout_response("mercadopago", checkout_id, checkout_url)
    ):
        raise _ManualProviderError("provider_unavailable", "provider preference does not match the frozen request")
    return ProviderCheckout(
        checkout_id=checkout_id,
        checkout_url=checkout_url,
        expires_at=_parse_expiry(response.get("date_of_expiration")),
    )


def _stripe_session_match(payload: dict[str, Any], candidate: object) -> ProviderCheckout | None:
    from app.payments import service as payment_service

    session = _plain_provider_object(candidate)
    line_items = payload.get("line_items")
    if not isinstance(line_items, list) or len(line_items) != 1 or not isinstance(line_items[0], dict):
        return None
    price_data = line_items[0].get("price_data")
    if not isinstance(price_data, dict):
        return None
    checkout_id = str(session.get("id") or "").strip()
    checkout_url = str(session.get("url") or "").strip()
    if (
        str(session.get("client_reference_id") or "") != str(payload.get("client_reference_id") or "")
        or not _exact_metadata(session.get("metadata"), payload.get("metadata"))
        or session.get("amount_total") != price_data.get("unit_amount")
        or str(session.get("currency") or "").lower() != str(price_data.get("currency") or "").lower()
        or not payment_service._valid_checkout_response("stripe", checkout_id, checkout_url)
    ):
        return None
    return ProviderCheckout(
        checkout_id=checkout_id,
        checkout_url=checkout_url,
        expires_at=_parse_expiry(session.get("expires_at")),
    )


def _stripe_session_references_purchase(payload: dict[str, Any], candidate: object) -> bool:
    session = _plain_provider_object(candidate)
    expected_reference = str(payload.get("client_reference_id") or "")
    expected_metadata = payload.get("metadata")
    actual_metadata = session.get("metadata")
    expected_purchase_id = (
        str(expected_metadata.get("purchase_id") or "") if isinstance(expected_metadata, dict) else ""
    )
    actual_purchase_id = str(actual_metadata.get("purchase_id") or "") if isinstance(actual_metadata, dict) else ""
    return (bool(expected_reference) and str(session.get("client_reference_id") or "") == expected_reference) or (
        bool(expected_purchase_id) and actual_purchase_id == expected_purchase_id
    )


async def _reconcile_stripe_session(
    sessions: object,
    claim: ClaimedCheckout,
    payload: dict[str, Any],
) -> ProviderCheckout | None:
    now = _utcnow()
    created_at = _aware_utc(claim.created_at)
    created_lower_bound = int((created_at - timedelta(minutes=5)).timestamp())
    created_upper_bound = int((now + timedelta(minutes=5)).timestamp())
    try:
        result = await asyncio.to_thread(
            sessions.list,  # type: ignore[attr-defined]
            {
                "created": {"gte": created_lower_bound, "lte": created_upper_bound},
                "limit": 100,
            },
            {"max_network_retries": 0},
        )
    except Exception as exc:
        try:
            _classify_provider_exception(exc)
        except _PermanentProviderError as classified:
            raise _ManualProviderError("provider_unavailable", "Stripe session lookup requires review") from classified
        raise

    result_data = result.get("data") if isinstance(result, dict) else getattr(result, "data", None)
    has_more = result.get("has_more") if isinstance(result, dict) else getattr(result, "has_more", False)
    if not isinstance(result_data, list):
        try:
            result_data = list(result_data)
        except (TypeError, ValueError):
            raise _ManualProviderError("provider_unavailable", "Stripe session lookup returned malformed results")
    matches: list[ProviderCheckout] = []
    mismatched_purchase = False
    for candidate in result_data:
        match = _stripe_session_match(payload, candidate)
        if match is not None:
            matches.append(match)
        elif _stripe_session_references_purchase(payload, candidate):
            mismatched_purchase = True
    if has_more:
        raise _ManualProviderError("provider_unavailable", "Stripe session lookup is incomplete")
    if len(matches) > 1:
        raise _ManualProviderError("provider_unavailable", "multiple Stripe sessions require manual review")
    if mismatched_purchase:
        raise _ManualProviderError("provider_unavailable", "Stripe session does not match the frozen request")
    return matches[0] if matches else None


async def _call_provider(claim: ClaimedCheckout) -> ProviderCheckout:
    """Create once or reconcile a retry without assuming provider idempotency forever."""
    from app.payments import service as payment_service

    payload = json.loads(claim.request_payload)
    if claim.provider == "mercadopago":
        sdk = payment_service._get_sdk()
        preference = sdk.preference()
        if claim.attempt_count > 1:
            return await _reconcile_mercadopago_preference(preference, claim, payload)
        request_options = _mp_request_options(idempotency_key=claim.provider_idempotency_key)
        try:
            result = await asyncio.to_thread(preference.create, payload, request_options)
        except Exception as exc:  # provider exceptions require fail-safe classification
            _classify_provider_exception(exc)
        status = _mp_status(result)
        _raise_for_ambiguous_result(status, action="creation")
        if status != 201:
            raise _PermanentProviderError("provider_rejected", "provider rejected the frozen request")
        if not isinstance(result.get("response"), dict):
            raise _TransientProviderError(
                "provider_unavailable",
                "provider accepted checkout creation but returned an ambiguous response",
            )
        response = result["response"]
        checkout_id = str(response.get("id") or "").strip()
        checkout_url = str(response.get("init_point") or response.get("sandbox_init_point") or "").strip()
        if not checkout_id or not checkout_url:
            raise _TransientProviderError(
                "provider_unavailable",
                "provider accepted checkout creation but omitted identity or URL",
            )
        if not payment_service._valid_checkout_response("mercadopago", checkout_id, checkout_url):
            raise _TransientProviderError(
                "provider_unavailable",
                "provider accepted checkout creation but returned an untrusted identity or URL",
            )
        return ProviderCheckout(
            checkout_id=checkout_id,
            checkout_url=checkout_url,
            expires_at=_parse_expiry(response.get("date_of_expiration")),
        )

    if not settings.STRIPE_SECRET_KEY:
        raise _PermanentProviderError("config_invalid", "Stripe is not configured")
    client = stripe.StripeClient(
        settings.STRIPE_SECRET_KEY,
        max_network_retries=0,
        http_client=stripe.RequestsClient(timeout=STRIPE_REQUEST_TIMEOUT_SECONDS),
    )
    sessions = client.v1.checkout.sessions
    if claim.attempt_count > 1:
        recovered = await _reconcile_stripe_session(sessions, claim, payload)
        if recovered is not None:
            return recovered
        age = _utcnow() - _aware_utc(claim.created_at)
        if age >= STRIPE_RETRY_HORIZON or claim.attempt_count >= MAX_CHECKOUT_ATTEMPTS:
            raise _ManualProviderError(
                "provider_unavailable",
                "Stripe session was not found inside the safe idempotency horizon",
            )
    try:
        session = await asyncio.to_thread(
            sessions.create,
            payload,
            {
                "max_network_retries": 0,
                "idempotency_key": claim.provider_idempotency_key,
            },
        )
    except Exception as exc:  # provider exceptions require fail-safe classification
        _classify_provider_exception(exc)
    session_data = _plain_provider_object(session)
    checkout_id = str(session_data.get("id") or "").strip()
    checkout_url = str(session_data.get("url") or "").strip()
    if not checkout_id or not checkout_url:
        raise _TransientProviderError(
            "provider_unavailable",
            "provider accepted checkout creation but omitted identity or URL",
        )
    if not payment_service._valid_checkout_response("stripe", checkout_id, checkout_url):
        raise _TransientProviderError(
            "provider_unavailable",
            "provider accepted checkout creation but returned an untrusted identity or URL",
        )
    return ProviderCheckout(
        checkout_id=checkout_id,
        checkout_url=checkout_url,
        expires_at=_parse_expiry(session_data.get("expires_at")),
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
    effective_now = now or _utcnow()
    lease_boundary = effective_now if now is not None else func.now()
    if claim.attempt_count >= MAX_CHECKOUT_ATTEMPTS:
        return await _terminalize_claim(
            db,
            claim,
            state="failed",
            code=code,
            detail=f"automatic retry budget exhausted; manual reconciliation required ({detail})",
            now=now,
            void_purchase=False,
        )
    retry_at = effective_now + _retry_delay(claim.attempt_count)
    result = await db.execute(
        update(PaymentCheckoutDispatch)
        .where(
            PaymentCheckoutDispatch.id == claim.dispatch_id,
            PaymentCheckoutDispatch.state == "pending",
            PaymentCheckoutDispatch.publisher_token == claim.publisher_token,
            PaymentCheckoutDispatch.publisher_lease_until > lease_boundary,
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
    now: datetime | None = None,
    void_purchase: bool = True,
) -> bool:
    effective_now = now or _utcnow()
    lease_boundary = effective_now if now is not None else func.now()
    dispatch = (
        await db.execute(
            select(PaymentCheckoutDispatch)
            .where(
                PaymentCheckoutDispatch.id == claim.dispatch_id,
                PaymentCheckoutDispatch.state == "pending",
                PaymentCheckoutDispatch.publisher_token == claim.publisher_token,
                PaymentCheckoutDispatch.publisher_lease_until > lease_boundary,
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
        now=effective_now,
        void_purchase=void_purchase,
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
            .where(
                PaymentCheckoutDispatch.id == claim.dispatch_id,
                PaymentCheckoutDispatch.state == "pending",
                PaymentCheckoutDispatch.publisher_token == claim.publisher_token,
                PaymentCheckoutDispatch.publisher_lease_until > func.now(),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if dispatch is None:
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
        claimed = await claim_checkout_dispatch(db, dispatch_id)
    except Exception:
        await db.rollback()
        return await _current_outcome(db, dispatch_id) if dispatch_id is not None else None
    if claimed is None:
        return await _current_outcome(db, dispatch_id) if dispatch_id is not None else None
    if isinstance(claimed, CheckoutOutcome):
        return claimed
    claim = claimed

    call = provider_call or _call_provider
    try:
        provider_checkout = await call(claim)
    except _PermanentProviderError as exc:
        await _terminalize_claim(db, claim, state="failed", code=exc.code, detail=exc.detail)
    except _ManualProviderError as exc:
        await _terminalize_claim(
            db,
            claim,
            state="failed",
            code=exc.code,
            detail=exc.detail,
            void_purchase=False,
        )
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
