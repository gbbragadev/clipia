from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import update

MP_CHECKOUT_ID = "1234567890-abcdef1234567890"
MP_CHECKOUT_URL = f"https://www.mercadopago.com/checkout?pref_id={MP_CHECKOUT_ID}"
STRIPE_CHECKOUT_ID = "cs_test_1234567890abcdef12345678"
STRIPE_CHECKOUT_URL = f"https://checkout.stripe.com/c/pay/{STRIPE_CHECKOUT_ID}"


async def _make_pending(db_session, verified_user, provider: str):
    from app.payments.checkout_outbox import create_or_resume_checkout

    return await create_or_resume_checkout(
        verified_user,
        "starter",
        provider,
        db_session,
        attempt_inline=False,
    )


async def _make_retry_due(db_session, dispatch_id: uuid.UUID) -> None:
    from app.db.models import PaymentCheckoutDispatch

    await db_session.execute(
        update(PaymentCheckoutDispatch)
        .where(PaymentCheckoutDispatch.id == dispatch_id)
        .values(next_attempt_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    )
    await db_session.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("idempotency_key", "expected_status"),
    [("   ", 400), ("x" * 201, 422)],
)
async def test_invalid_http_idempotency_key_is_a_stable_client_error(
    client,
    verified_user,
    auth_headers,
    idempotency_key,
    expected_status,
):
    response = await client.post(
        "/api/v1/credits/checkout",
        json={"package": "starter", "provider": "mercadopago"},
        headers={**auth_headers(verified_user), "Idempotency-Key": idempotency_key},
    )

    assert response.status_code == expected_status
    assert response.status_code < 500
    if expected_status == 400:
        assert response.json() == {"detail": "invalid_idempotency_key"}


def test_idempotency_key_rejects_delete_control_character():
    from app.payments.checkout_outbox import InvalidCheckoutIdempotencyKey, _normalize_request_key

    with pytest.raises(InvalidCheckoutIdempotencyKey):
        _normalize_request_key(uuid.uuid4(), "unsafe\x7fkey")


def test_checkout_openapi_documents_typed_header_pending_response_and_state_enum(app):
    schema = app.openapi()
    operation = schema["paths"]["/api/v1/credits/checkout"]["post"]
    header = next(parameter for parameter in operation["parameters"] if parameter["in"] == "header")

    assert header["name"] == "Idempotency-Key"
    assert header["required"] is False
    string_schema = next(option for option in header["schema"]["anyOf"] if option.get("type") == "string")
    assert string_schema["maxLength"] == 200
    assert operation["responses"]["202"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/CheckoutStatusResponse"
    }
    assert schema["components"]["schemas"]["CheckoutStatusResponse"]["properties"]["state"]["enum"] == [
        "pending",
        "ready",
        "failed",
        "cancelled",
    ]


@pytest.mark.asyncio
async def test_checkout_cors_preflight_allows_idempotency_key(client):
    response = await client.options(
        "/api/v1/credits/checkout",
        headers={
            "Origin": "http://localhost:3003",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,idempotency-key",
        },
    )

    assert response.status_code == 200
    assert "idempotency-key" in response.headers["access-control-allow-headers"].lower()


@pytest.mark.parametrize("status_code", [408, 409, 424, 425])
def test_ambiguous_http_status_is_classified_as_transient(status_code):
    from app.payments.checkout_outbox import _classify_provider_exception, _TransientProviderError

    error = RuntimeError("request timeout")
    error.status_code = status_code

    with pytest.raises(_TransientProviderError):
        _classify_provider_exception(error)


@pytest.mark.asyncio
async def test_expired_claim_cannot_schedule_retry_or_terminalize_after_reclaim(db_session, verified_user):
    from app.db.models import PaymentCheckoutDispatch
    from app.payments.checkout_outbox import (
        _schedule_retry,
        _terminalize_claim,
        claim_checkout_dispatch,
    )

    scheduled = await _make_pending(db_session, verified_user, "stripe")
    claimed_at = datetime.now(timezone.utc)
    expired = await claim_checkout_dispatch(
        db_session,
        scheduled.dispatch_id,
        now=claimed_at,
        lease_duration=timedelta(seconds=1),
    )
    assert expired is not None
    assert (
        await _schedule_retry(
            db_session,
            expired,
            code="provider_unavailable",
            detail="late publisher",
            now=claimed_at + timedelta(seconds=2),
        )
        is False
    )
    still_owned = await db_session.get(PaymentCheckoutDispatch, scheduled.dispatch_id, populate_existing=True)
    assert still_owned.publisher_token == expired.publisher_token

    reclaimed = await claim_checkout_dispatch(
        db_session,
        scheduled.dispatch_id,
        now=claimed_at + timedelta(seconds=2),
    )
    assert reclaimed is not None
    assert reclaimed.publisher_token != expired.publisher_token
    assert (
        await _terminalize_claim(
            db_session,
            expired,
            state="failed",
            code="provider_rejected",
            detail="stale publisher",
            now=claimed_at + timedelta(seconds=3),
        )
        is False
    )
    persisted = await db_session.get(PaymentCheckoutDispatch, scheduled.dispatch_id, populate_existing=True)
    assert persisted.state == "pending"
    assert persisted.publisher_token == reclaimed.publisher_token


@pytest.mark.asyncio
async def test_claim_reclaim_uses_database_clock_instead_of_skewed_process_clock(
    db_session,
    verified_user,
    monkeypatch,
):
    from app.payments import checkout_outbox
    from app.payments.checkout_outbox import claim_checkout_dispatch

    scheduled = await _make_pending(db_session, verified_user, "stripe")
    database_aligned_now = datetime.now(timezone.utc)
    first = await claim_checkout_dispatch(
        db_session,
        scheduled.dispatch_id,
        now=database_aligned_now,
        lease_duration=timedelta(minutes=1),
    )
    assert first is not None

    monkeypatch.setattr(
        checkout_outbox,
        "_utcnow",
        lambda: database_aligned_now + timedelta(days=1),
    )

    assert await claim_checkout_dispatch(db_session, scheduled.dispatch_id) is None


@pytest.mark.asyncio
async def test_mp_408_then_retry_recovers_only_through_search_and_get(
    db_session,
    verified_user,
    monkeypatch,
):
    from app.payments.checkout_outbox import dispatch_checkout

    created = await _make_pending(db_session, verified_user, "mercadopago")
    calls = {"create": 0, "search": 0, "get": 0}
    frozen_payload: dict[str, object] = {}

    class Preference:
        @staticmethod
        def create(payload, request_options=None):
            calls["create"] += 1
            frozen_payload.update(payload)
            assert request_options.max_retries == 0
            return {"status": 408, "response": {"message": "timeout"}}

        @staticmethod
        def search(filters, request_options=None):
            calls["search"] += 1
            assert filters == {"external_reference": frozen_payload["external_reference"]}
            return {"status": 200, "response": {"elements": [{"id": MP_CHECKOUT_ID}]}}

        @staticmethod
        def get(preference_id, request_options=None):
            calls["get"] += 1
            assert preference_id == MP_CHECKOUT_ID
            return {
                "status": 200,
                "response": {
                    "id": MP_CHECKOUT_ID,
                    "init_point": MP_CHECKOUT_URL,
                    "external_reference": frozen_payload["external_reference"],
                    "metadata": frozen_payload["metadata"],
                    "items": frozen_payload["items"],
                },
            }

    monkeypatch.setattr(
        "app.payments.service._get_sdk",
        lambda: SimpleNamespace(preference=lambda: Preference()),
    )

    first = await dispatch_checkout(db_session, created.dispatch_id)
    assert first.state == "pending"
    await _make_retry_due(db_session, created.dispatch_id)
    recovered = await dispatch_checkout(db_session, created.dispatch_id)

    assert recovered.state == "ready"
    assert recovered.checkout_url == MP_CHECKOUT_URL
    assert calls == {"create": 1, "search": 1, "get": 1}


@pytest.mark.asyncio
@pytest.mark.parametrize(("matches", "expected_state"), [(0, "pending"), (2, "failed")])
async def test_mp_retry_zero_or_multiple_matches_never_posts_again_and_fails_safe(
    db_session,
    verified_user,
    monkeypatch,
    matches,
    expected_state,
):
    from app.db.models import CreditPurchase
    from app.payments.checkout_outbox import dispatch_checkout

    created = await _make_pending(db_session, verified_user, "mercadopago")
    calls = {"create": 0, "search": 0, "get": 0}

    class Preference:
        @staticmethod
        def create(_payload, request_options=None):
            calls["create"] += 1
            return {"status": 500, "response": {}}

        @staticmethod
        def search(_filters, request_options=None):
            calls["search"] += 1
            return {
                "status": 200,
                "response": {"elements": [{"id": f"{MP_CHECKOUT_ID}-{index}"} for index in range(matches)]},
            }

        @staticmethod
        def get(_preference_id, request_options=None):
            calls["get"] += 1
            raise AssertionError("zero/multiple matches must not be selected")

    monkeypatch.setattr(
        "app.payments.service._get_sdk",
        lambda: SimpleNamespace(preference=lambda: Preference()),
    )

    assert (await dispatch_checkout(db_session, created.dispatch_id)).state == "pending"
    await _make_retry_due(db_session, created.dispatch_id)
    retry = await dispatch_checkout(db_session, created.dispatch_id)

    assert retry.state == expected_state
    assert calls == {"create": 1, "search": 1, "get": 0}
    purchase = await db_session.get(CreditPurchase, created.purchase_id, populate_existing=True)
    assert purchase.payment_state == "pending"
    assert purchase.status == "pending"


@pytest.mark.asyncio
async def test_mp_retry_rejects_preference_with_mismatched_frozen_amount_without_new_post(
    db_session,
    verified_user,
    monkeypatch,
):
    from app.db.models import CreditPurchase, PaymentCheckoutDispatch
    from app.payments.checkout_outbox import dispatch_checkout

    created = await _make_pending(db_session, verified_user, "mercadopago")
    dispatch = await db_session.get(PaymentCheckoutDispatch, created.dispatch_id)
    payload = json.loads(dispatch.request_payload)
    dispatch.attempt_count = 1
    dispatch.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db_session.commit()
    calls = {"create": 0, "search": 0, "get": 0}
    mismatched_items = [dict(payload["items"][0], unit_price=999.99)]

    class Preference:
        @staticmethod
        def create(_payload, request_options=None):
            calls["create"] += 1
            raise AssertionError("a retry must never create another preference")

        @staticmethod
        def search(_filters, request_options=None):
            calls["search"] += 1
            return {"status": 200, "response": {"elements": [{"id": MP_CHECKOUT_ID}]}}

        @staticmethod
        def get(_preference_id, request_options=None):
            calls["get"] += 1
            return {
                "status": 200,
                "response": {
                    "id": MP_CHECKOUT_ID,
                    "init_point": MP_CHECKOUT_URL,
                    "external_reference": payload["external_reference"],
                    "metadata": payload["metadata"],
                    "items": mismatched_items,
                },
            }

    monkeypatch.setattr(
        "app.payments.service._get_sdk",
        lambda: SimpleNamespace(preference=lambda: Preference()),
    )

    outcome = await dispatch_checkout(db_session, created.dispatch_id)

    assert outcome.state == "failed"
    assert calls == {"create": 0, "search": 1, "get": 1}
    purchase = await db_session.get(CreditPurchase, created.purchase_id, populate_existing=True)
    assert purchase.payment_state == "pending"


def _stripe_session(payload: dict[str, object], checkout_id: str = STRIPE_CHECKOUT_ID):
    return SimpleNamespace(
        id=checkout_id,
        url=f"https://checkout.stripe.com/c/pay/{checkout_id}",
        client_reference_id=payload["client_reference_id"],
        metadata=payload["metadata"],
        amount_total=payload["line_items"][0]["price_data"]["unit_amount"],
        currency=payload["line_items"][0]["price_data"]["currency"],
        expires_at=None,
    )


def _install_fake_stripe_client(monkeypatch, *, create_result, listed_sessions):
    calls: dict[str, object] = {"create": 0, "list": 0, "clients": [], "http_timeouts": []}

    class FakeRequestsClient:
        def __init__(self, *, timeout):
            calls["http_timeouts"].append(timeout)

    class Sessions:
        def create(self, params, options=None):
            calls["create"] += 1
            calls["create_options"] = options
            calls["create_payload"] = params
            if isinstance(create_result, BaseException):
                raise create_result
            return create_result(params) if callable(create_result) else create_result

        def list(self, params, options=None):
            calls["list"] += 1
            calls["list_params"] = params
            calls["list_options"] = options
            payload = json.loads(calls.get("frozen_payload", "{}"))
            sessions = listed_sessions(payload) if callable(listed_sessions) else listed_sessions
            return SimpleNamespace(data=sessions, has_more=False)

    class FakeStripeClient:
        def __init__(self, api_key, **kwargs):
            calls["clients"].append((api_key, kwargs))
            self.v1 = SimpleNamespace(checkout=SimpleNamespace(sessions=Sessions()))

    monkeypatch.setattr("app.payments.checkout_outbox.stripe.RequestsClient", FakeRequestsClient)
    monkeypatch.setattr("app.payments.checkout_outbox.stripe.StripeClient", FakeStripeClient)
    return calls


@pytest.mark.asyncio
async def test_stripe_retry_rejects_same_purchase_with_mismatched_amount_without_post(
    db_session,
    verified_user,
    monkeypatch,
):
    from app.config import settings
    from app.db.models import CreditPurchase, PaymentCheckoutDispatch
    from app.payments.checkout_outbox import dispatch_checkout

    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_checkout")
    created = await _make_pending(db_session, verified_user, "stripe")
    dispatch = await db_session.get(PaymentCheckoutDispatch, created.dispatch_id)
    payload = json.loads(dispatch.request_payload)
    dispatch.attempt_count = 1
    dispatch.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db_session.commit()
    suspicious = _stripe_session(payload)
    suspicious.amount_total += 1
    calls = _install_fake_stripe_client(
        monkeypatch,
        create_result=lambda frozen: _stripe_session(frozen),
        listed_sessions=[suspicious],
    )
    calls["frozen_payload"] = dispatch.request_payload

    outcome = await dispatch_checkout(db_session, created.dispatch_id)

    assert outcome.state == "failed"
    assert calls["list"] == 1
    assert calls["create"] == 0
    purchase = await db_session.get(CreditPurchase, created.purchase_id, populate_existing=True)
    assert purchase.payment_state == "pending"


@pytest.mark.asyncio
async def test_stripe_retry_recovers_existing_session_read_only_with_bounded_transport(
    db_session,
    verified_user,
    monkeypatch,
):
    from app.config import settings
    from app.payments.checkout_outbox import (
        CHECKOUT_LEASE_DURATION,
        STRIPE_REQUEST_TIMEOUT_SECONDS,
        dispatch_checkout,
    )

    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_checkout")
    created = await _make_pending(db_session, verified_user, "stripe")
    calls = _install_fake_stripe_client(
        monkeypatch,
        create_result=TimeoutError("ambiguous create timeout"),
        listed_sessions=lambda payload: [_stripe_session(payload)],
    )
    from app.db.models import PaymentCheckoutDispatch

    dispatch = await db_session.get(PaymentCheckoutDispatch, created.dispatch_id)
    calls["frozen_payload"] = dispatch.request_payload
    provider_idempotency_key = dispatch.provider_idempotency_key

    assert (await dispatch_checkout(db_session, created.dispatch_id)).state == "pending"
    await _make_retry_due(db_session, created.dispatch_id)
    recovered = await dispatch_checkout(db_session, created.dispatch_id)

    assert recovered.state == "ready"
    assert calls["create"] == 1
    assert calls["list"] == 1
    assert calls["create_options"] == {"max_network_retries": 0, "idempotency_key": provider_idempotency_key}
    assert calls["list_options"] == {"max_network_retries": 0}
    assert calls["http_timeouts"] == [STRIPE_REQUEST_TIMEOUT_SECONDS, STRIPE_REQUEST_TIMEOUT_SECONDS]
    assert calls["clients"][0][1]["max_network_retries"] == 0
    assert STRIPE_REQUEST_TIMEOUT_SECONDS * 4 < CHECKOUT_LEASE_DURATION.total_seconds()


@pytest.mark.asyncio
async def test_stripe_retry_with_no_match_reposts_only_inside_horizon_with_same_key(
    db_session,
    verified_user,
    monkeypatch,
):
    from app.config import settings
    from app.db.models import PaymentCheckoutDispatch
    from app.payments.checkout_outbox import dispatch_checkout

    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_checkout")
    created = await _make_pending(db_session, verified_user, "stripe")
    dispatch = await db_session.get(PaymentCheckoutDispatch, created.dispatch_id)
    dispatch.attempt_count = 1
    dispatch.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    frozen_payload = dispatch.request_payload
    provider_key = dispatch.provider_idempotency_key
    await db_session.commit()
    calls = _install_fake_stripe_client(
        monkeypatch,
        create_result=lambda payload: _stripe_session(payload),
        listed_sessions=[],
    )
    calls["frozen_payload"] = frozen_payload

    outcome = await dispatch_checkout(db_session, created.dispatch_id)

    assert outcome.state == "ready"
    assert calls["list"] == 1
    assert calls["create"] == 1
    assert calls["create_options"] == {"max_network_retries": 0, "idempotency_key": provider_key}


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["late_zero", "multiple"])
async def test_stripe_retry_never_posts_late_or_after_multiple_read_only_matches(
    db_session,
    verified_user,
    monkeypatch,
    mode,
):
    from app.config import settings
    from app.db.models import CreditPurchase, PaymentCheckoutDispatch
    from app.payments.checkout_outbox import STRIPE_RETRY_HORIZON, dispatch_checkout

    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_checkout")
    created = await _make_pending(db_session, verified_user, "stripe")
    dispatch = await db_session.get(PaymentCheckoutDispatch, created.dispatch_id)
    payload = json.loads(dispatch.request_payload)
    dispatch.attempt_count = 1
    dispatch.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    if mode == "late_zero":
        dispatch.created_at = datetime.now(timezone.utc) - STRIPE_RETRY_HORIZON - timedelta(minutes=1)
        listed = []
    else:
        listed = [
            _stripe_session(payload, f"{STRIPE_CHECKOUT_ID}a"),
            _stripe_session(payload, f"{STRIPE_CHECKOUT_ID}b"),
        ]
    await db_session.commit()

    calls = _install_fake_stripe_client(
        monkeypatch,
        create_result=lambda frozen: _stripe_session(frozen),
        listed_sessions=listed,
    )
    calls["frozen_payload"] = dispatch.request_payload

    outcome = await dispatch_checkout(db_session, created.dispatch_id)

    assert outcome.state == "failed"
    assert calls["list"] == 1
    assert calls["create"] == 0
    purchase = await db_session.get(CreditPurchase, created.purchase_id, populate_existing=True)
    assert purchase.payment_state == "pending"
    assert purchase.status == "pending"


@pytest.mark.asyncio
async def test_retry_budget_exhaustion_stops_loop_without_voiding_ambiguous_purchase(
    db_session,
    verified_user,
):
    from app.db.models import CreditPurchase, PaymentCheckoutDispatch
    from app.payments.checkout_outbox import MAX_CHECKOUT_ATTEMPTS, dispatch_checkout

    created = await _make_pending(db_session, verified_user, "stripe")
    dispatch = await db_session.get(PaymentCheckoutDispatch, created.dispatch_id)
    dispatch.attempt_count = MAX_CHECKOUT_ATTEMPTS - 1
    dispatch.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db_session.commit()
    provider_calls = 0

    async def ambiguous(_claim):
        nonlocal provider_calls
        provider_calls += 1
        raise TimeoutError("unknown provider outcome")

    outcome = await dispatch_checkout(db_session, created.dispatch_id, provider_call=ambiguous)

    assert outcome.state == "failed"
    assert provider_calls == 1
    purchase = await db_session.get(CreditPurchase, created.purchase_id, populate_existing=True)
    assert purchase.payment_state == "pending"
    assert purchase.status == "pending"


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal_state", ["paid", "refunded", "void"])
async def test_terminal_purchase_before_claim_cancels_without_external_call_and_preserves_state(
    db_session,
    verified_user,
    terminal_state,
):
    from app.db.models import CreditPurchase
    from app.payments.checkout_outbox import dispatch_checkout
    from app.payments.states import payment_state_values

    created = await _make_pending(db_session, verified_user, "stripe")
    await db_session.execute(
        update(CreditPurchase)
        .where(CreditPurchase.id == created.purchase_id)
        .values(**payment_state_values(terminal_state))
    )
    await db_session.commit()
    provider_calls = 0

    async def provider(_claim):
        nonlocal provider_calls
        provider_calls += 1
        raise AssertionError("terminal purchase must not create a checkout")

    outcome = await dispatch_checkout(db_session, created.dispatch_id, provider_call=provider)

    assert outcome.state == "cancelled"
    assert provider_calls == 0
    purchase = await db_session.get(CreditPurchase, created.purchase_id, populate_existing=True)
    assert purchase.payment_state == terminal_state


@pytest.mark.asyncio
async def test_reconciler_continues_after_poison_row_and_counts_both_outcomes(
    test_db,
    db_session,
    verified_user,
):
    from app.db.models import PaymentCheckoutDispatch
    from app.payments.checkout_outbox import ProviderCheckout, reconcile_checkout_dispatches

    poison = await _make_pending(db_session, verified_user, "stripe")
    valid = await _make_pending(db_session, verified_user, "stripe")
    poison_dispatch = await db_session.get(PaymentCheckoutDispatch, poison.dispatch_id)
    valid_dispatch = await db_session.get(PaymentCheckoutDispatch, valid.dispatch_id)
    poison_dispatch.request_payload = poison_dispatch.request_payload.replace("starter", "tampered")
    poison_dispatch.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=2)
    valid_dispatch.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db_session.commit()
    calls = 0

    async def provider(_claim):
        nonlocal calls
        calls += 1
        checkout_id = f"{STRIPE_CHECKOUT_ID}{calls}"
        return ProviderCheckout(checkout_id, f"https://checkout.stripe.com/c/pay/{checkout_id}")

    counts = await reconcile_checkout_dispatches(test_db["session_factory"], limit=2, provider_call=provider)

    assert counts == {"ready": 1, "pending": 0, "failed": 1, "cancelled": 0}
    assert calls == 1
