from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select, update

MP_CHECKOUT_ID = "1234567890-abcdef1234567890"
MP_CHECKOUT_URL = f"https://www.mercadopago.com/checkout?pref_id={MP_CHECKOUT_ID}"
STRIPE_CHECKOUT_ID = "cs_test_1234567890abcdef12345678"
STRIPE_CHECKOUT_URL = f"https://checkout.stripe.com/c/pay/{STRIPE_CHECKOUT_ID}"


def _provider_checkout(provider: str, *, suffix: str = ""):
    from app.payments.checkout_outbox import ProviderCheckout

    if provider == "stripe":
        checkout_id = f"{STRIPE_CHECKOUT_ID}{suffix}"
        return ProviderCheckout(checkout_id, f"https://checkout.stripe.com/c/pay/{checkout_id}")
    checkout_id = f"{MP_CHECKOUT_ID}{suffix}"
    return ProviderCheckout(checkout_id, f"https://www.mercadopago.com/checkout?pref_id={checkout_id}")


@pytest.mark.asyncio
async def test_initial_commit_failure_calls_no_provider_and_persists_nothing(db_session, verified_user, monkeypatch):
    from app.db.models import CreditPurchase, PaymentCheckoutDispatch
    from app.payments import checkout_outbox

    provider_calls = 0

    async def unexpected_provider_call(_claim):
        nonlocal provider_calls
        provider_calls += 1
        raise AssertionError("provider must not run before the durable commit")

    async def fail_commit():
        raise RuntimeError("initial commit unavailable")

    monkeypatch.setattr(checkout_outbox, "_call_provider", unexpected_provider_call)
    monkeypatch.setattr(db_session, "commit", fail_commit)

    with pytest.raises(RuntimeError, match="initial commit unavailable"):
        await checkout_outbox.create_or_resume_checkout(
            verified_user,
            "starter",
            "mercadopago",
            db_session,
        )

    await db_session.rollback()
    assert provider_calls == 0
    assert await db_session.scalar(select(func.count()).select_from(CreditPurchase)) == 0
    assert await db_session.scalar(select(func.count()).select_from(PaymentCheckoutDispatch)) == 0


@pytest.mark.asyncio
async def test_crash_after_initial_commit_is_reconciled_to_ready(test_db, db_session, verified_user):
    from app.db.models import CreditPurchase, PaymentCheckoutDispatch
    from app.payments.checkout_outbox import create_or_resume_checkout, reconcile_checkout_dispatches

    created = await create_or_resume_checkout(
        verified_user,
        "starter",
        "stripe",
        db_session,
        attempt_inline=False,
    )
    assert created.state == "pending"
    assert (await db_session.get(CreditPurchase, created.purchase_id)).mp_preference_id is None

    calls = []

    async def provider(claim):
        calls.append(claim)
        return _provider_checkout("stripe")

    counts = await reconcile_checkout_dispatches(test_db["session_factory"], provider_call=provider)

    assert counts == {"ready": 1, "pending": 0, "failed": 0, "cancelled": 0}
    assert len(calls) == 1
    async with test_db["session_factory"]() as verify:
        dispatch = await verify.get(PaymentCheckoutDispatch, created.dispatch_id)
        purchase = await verify.get(CreditPurchase, created.purchase_id)
        assert dispatch.state == "ready"
        assert dispatch.checkout_url == STRIPE_CHECKOUT_URL
        assert purchase.mp_preference_id == STRIPE_CHECKOUT_ID
        assert purchase.payment_state == "pending"


@pytest.mark.asyncio
async def test_expired_lease_can_be_reclaimed_and_stale_token_cannot_finalize(db_session, verified_user):
    from app.db.models import PaymentCheckoutDispatch
    from app.payments.checkout_outbox import (
        claim_checkout_dispatch,
        create_or_resume_checkout,
        finalize_checkout_dispatch,
    )

    created = await create_or_resume_checkout(
        verified_user,
        "starter",
        "stripe",
        db_session,
        attempt_inline=False,
    )
    first_now = datetime.now(timezone.utc)
    first = await claim_checkout_dispatch(db_session, created.dispatch_id, now=first_now)
    assert first is not None
    assert await claim_checkout_dispatch(db_session, created.dispatch_id, now=first_now) is None

    second = await claim_checkout_dispatch(
        db_session,
        created.dispatch_id,
        now=first_now + timedelta(minutes=3),
    )
    assert second is not None
    assert second.publisher_token != first.publisher_token

    provider_checkout = _provider_checkout("stripe")
    assert await finalize_checkout_dispatch(db_session, first, provider_checkout) is False
    assert await finalize_checkout_dispatch(db_session, second, provider_checkout) is True
    persisted = await db_session.get(PaymentCheckoutDispatch, created.dispatch_id, populate_existing=True)
    assert persisted.state == "ready"


@pytest.mark.asyncio
async def test_unknown_provider_failure_stays_pending_and_retry_reuses_frozen_request(db_session, verified_user):
    from app.db.models import CreditPurchase, PaymentCheckoutDispatch
    from app.payments.checkout_outbox import create_or_resume_checkout, dispatch_checkout

    created = await create_or_resume_checkout(
        verified_user,
        "starter",
        "mercadopago",
        db_session,
        attempt_inline=False,
    )
    seen = []

    async def unknown_failure(claim):
        seen.append((claim.provider_idempotency_key, claim.request_payload, claim.request_payload_hash))
        raise RuntimeError("unknown provider outcome with secret sk_should_not_persist")

    pending = await dispatch_checkout(db_session, created.dispatch_id, provider_call=unknown_failure)
    assert pending.state == "pending"
    dispatch = await db_session.get(PaymentCheckoutDispatch, created.dispatch_id, populate_existing=True)
    purchase = await db_session.get(CreditPurchase, created.purchase_id, populate_existing=True)
    assert dispatch.state == "pending"
    assert dispatch.next_attempt_at > dispatch.last_attempt_at
    assert "sk_should_not_persist" not in (dispatch.error_detail or "")
    assert purchase.payment_state == "pending"
    assert purchase.status == "pending"

    dispatch.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db_session.commit()

    async def succeeds(claim):
        seen.append((claim.provider_idempotency_key, claim.request_payload, claim.request_payload_hash))
        return _provider_checkout("mercadopago")

    ready = await dispatch_checkout(db_session, created.dispatch_id, provider_call=succeeds)
    assert ready.state == "ready"
    assert seen[0] == seen[1]


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["timeout", "malformed_201", 408, 424, 429, 500])
async def test_mp_ambiguous_first_outcomes_never_void_or_credit_and_backoff_is_capped(
    db_session, verified_user, monkeypatch, outcome
):
    from app.db.models import CreditPurchase, PaymentCheckoutDispatch, User
    from app.payments.checkout_outbox import MAX_RETRY_DELAY_SECONDS, create_or_resume_checkout, dispatch_checkout

    created = await create_or_resume_checkout(
        verified_user,
        "starter",
        "mercadopago",
        db_session,
        attempt_inline=False,
    )
    dispatch = await db_session.get(PaymentCheckoutDispatch, created.dispatch_id)

    class Preference:
        @staticmethod
        def create(_payload, request_options=None):
            if outcome == "timeout":
                raise TimeoutError("ambiguous timeout")
            if outcome == "malformed_201":
                return {"status": 201, "response": {}}
            return {"status": outcome, "response": {"message": "ambiguous"}}

    class SDK:
        @staticmethod
        def preference():
            return Preference()

    monkeypatch.setattr("app.payments.service._get_sdk", lambda: SDK())
    result = await dispatch_checkout(db_session, created.dispatch_id)

    assert result.state == "pending"
    dispatch = await db_session.get(PaymentCheckoutDispatch, created.dispatch_id, populate_existing=True)
    purchase = await db_session.get(CreditPurchase, created.purchase_id, populate_existing=True)
    user = await db_session.get(User, verified_user.id, populate_existing=True)
    assert dispatch.attempt_count == 1
    last_attempt_at = dispatch.last_attempt_at
    next_attempt_at = dispatch.next_attempt_at
    if last_attempt_at.tzinfo is None:
        last_attempt_at = last_attempt_at.replace(tzinfo=timezone.utc)
    if next_attempt_at.tzinfo is None:
        next_attempt_at = next_attempt_at.replace(tzinfo=timezone.utc)
    assert timedelta(0) < next_attempt_at - last_attempt_at <= timedelta(seconds=MAX_RETRY_DELAY_SECONDS + 1)
    assert purchase.payment_state == "pending"
    assert purchase.mp_preference_id is None
    assert user.credits == 5


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["mercadopago", "stripe"])
async def test_reclaimed_claim_reuses_identical_transport_key_and_frozen_payload(db_session, verified_user, provider):
    from app.db.models import PaymentCheckoutDispatch
    from app.payments.checkout_outbox import (
        claim_checkout_dispatch,
        create_or_resume_checkout,
    )

    created = await create_or_resume_checkout(
        verified_user,
        "starter",
        provider,
        db_session,
        attempt_inline=False,
    )
    started = datetime.now(timezone.utc)
    first = await claim_checkout_dispatch(db_session, created.dispatch_id, now=started)
    assert first is not None
    second = await claim_checkout_dispatch(
        db_session,
        created.dispatch_id,
        now=started + timedelta(minutes=3),
    )
    assert second is not None

    dispatch = await db_session.get(PaymentCheckoutDispatch, created.dispatch_id, populate_existing=True)
    assert first.provider_idempotency_key == second.provider_idempotency_key == dispatch.provider_idempotency_key
    assert first.request_payload == second.request_payload == dispatch.request_payload
    assert first.request_payload_hash == second.request_payload_hash == dispatch.request_payload_hash


@pytest.mark.asyncio
async def test_binding_commit_failure_remains_recoverable_and_converges(db_session, verified_user, monkeypatch):
    from app.db.models import CreditPurchase, PaymentCheckoutDispatch
    from app.payments.checkout_outbox import create_or_resume_checkout, dispatch_checkout

    created = await create_or_resume_checkout(
        verified_user,
        "starter",
        "stripe",
        db_session,
        attempt_inline=False,
    )
    seen = []

    async def provider(claim):
        seen.append((claim.provider_idempotency_key, claim.request_payload))
        return _provider_checkout("stripe")

    original_commit = db_session.commit
    commit_calls = 0

    async def fail_binding_once():
        nonlocal commit_calls
        commit_calls += 1
        if commit_calls == 2:
            raise RuntimeError("binding commit failed")
        await original_commit()

    monkeypatch.setattr(db_session, "commit", fail_binding_once)
    pending = await dispatch_checkout(db_session, created.dispatch_id, provider_call=provider)
    assert pending.state == "pending"
    purchase = await db_session.get(CreditPurchase, created.purchase_id, populate_existing=True)
    dispatch = await db_session.get(PaymentCheckoutDispatch, created.dispatch_id, populate_existing=True)
    assert purchase.payment_state == "pending"
    assert purchase.mp_preference_id is None
    assert dispatch.state == "pending"

    dispatch.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db_session.commit()
    ready = await dispatch_checkout(db_session, created.dispatch_id, provider_call=provider)
    assert ready.state == "ready"
    assert seen[0] == seen[1]


@pytest.mark.asyncio
async def test_provider_accepts_then_process_crashes_and_expired_lease_replays_once(db_session, verified_user):
    from app.db.models import CreditPurchase, PaymentCheckoutDispatch
    from app.payments.checkout_outbox import (
        claim_checkout_dispatch,
        create_or_resume_checkout,
        dispatch_checkout,
        finalize_checkout_dispatch,
    )

    class SimulatedProcessDeath(BaseException):
        pass

    created = await create_or_resume_checkout(
        verified_user,
        "starter",
        "stripe",
        db_session,
        attempt_inline=False,
    )
    provider_calls = []
    provider_checkout = _provider_checkout("stripe")

    async def accepted_then_process_dies(claim):
        provider_calls.append((claim.provider_idempotency_key, claim.request_payload))
        raise SimulatedProcessDeath

    with pytest.raises(SimulatedProcessDeath):
        await dispatch_checkout(db_session, created.dispatch_id, provider_call=accepted_then_process_dies)

    leased = await db_session.get(PaymentCheckoutDispatch, created.dispatch_id, populate_existing=True)
    assert leased.state == "pending"
    assert leased.publisher_token is not None
    lease_until = leased.publisher_lease_until
    if lease_until.tzinfo is None:
        lease_until = lease_until.replace(tzinfo=timezone.utc)

    replay = await claim_checkout_dispatch(
        db_session,
        created.dispatch_id,
        now=lease_until + timedelta(seconds=1),
    )
    assert replay is not None
    provider_calls.append((replay.provider_idempotency_key, replay.request_payload))
    assert await finalize_checkout_dispatch(db_session, replay, provider_checkout) is True

    dispatch = await db_session.get(PaymentCheckoutDispatch, created.dispatch_id, populate_existing=True)
    purchase = await db_session.get(CreditPurchase, created.purchase_id, populate_existing=True)
    assert provider_calls[0] == provider_calls[1]
    assert dispatch.state == "ready"
    assert dispatch.provider_checkout_id == STRIPE_CHECKOUT_ID
    assert purchase.mp_preference_id == STRIPE_CHECKOUT_ID


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider", "provider_checkout"),
    [
        ("stripe", SimpleNamespace(checkout_id="garbage", checkout_url=STRIPE_CHECKOUT_URL, expires_at=None)),
        (
            "mercadopago",
            SimpleNamespace(
                checkout_id=MP_CHECKOUT_ID,
                checkout_url="https://www.mercadopago.com.evil.example/checkout",
                expires_at=None,
            ),
        ),
    ],
)
async def test_permanent_invalid_provider_identity_fails_dispatch_and_voids_purchase(
    db_session, verified_user, provider, provider_checkout
):
    from app.db.models import CreditPurchase, PaymentCheckoutDispatch
    from app.payments.checkout_outbox import create_or_resume_checkout, dispatch_checkout

    created = await create_or_resume_checkout(
        verified_user,
        "starter",
        provider,
        db_session,
        attempt_inline=False,
    )

    async def invalid(_claim):
        return provider_checkout

    failed = await dispatch_checkout(db_session, created.dispatch_id, provider_call=invalid)
    assert failed.state == "failed"
    assert failed.checkout_url is None
    dispatch = await db_session.get(PaymentCheckoutDispatch, created.dispatch_id, populate_existing=True)
    purchase = await db_session.get(CreditPurchase, created.purchase_id, populate_existing=True)
    assert dispatch.error_code == "invalid_response"
    assert purchase.payment_state == "void"
    assert purchase.mp_preference_id is None


@pytest.mark.asyncio
async def test_provider_checkout_identity_collision_fails_closed_without_returning_url(db_session, verified_user):
    from app.db.models import CreditPurchase, PaymentCheckoutDispatch
    from app.payments.checkout_outbox import create_or_resume_checkout, dispatch_checkout

    async def same_provider_object(_claim):
        return _provider_checkout("stripe")

    first = await create_or_resume_checkout(
        verified_user,
        "starter",
        "stripe",
        db_session,
        provider_call=same_provider_object,
    )
    second = await create_or_resume_checkout(
        verified_user,
        "starter",
        "stripe",
        db_session,
        attempt_inline=False,
    )
    collision = await dispatch_checkout(db_session, second.dispatch_id, provider_call=same_provider_object)

    assert first.state == "ready"
    assert collision.state == "failed"
    assert collision.checkout_url is None
    first_dispatch = await db_session.get(PaymentCheckoutDispatch, first.dispatch_id, populate_existing=True)
    second_dispatch = await db_session.get(PaymentCheckoutDispatch, second.dispatch_id, populate_existing=True)
    second_purchase = await db_session.get(CreditPurchase, second.purchase_id, populate_existing=True)
    assert first_dispatch.checkout_url == STRIPE_CHECKOUT_URL
    assert second_dispatch.error_code == "identity_collision"
    assert second_purchase.payment_state == "void"


@pytest.mark.asyncio
@pytest.mark.parametrize("payment_state", ["paid", "refunded"])
async def test_finalizer_accepts_identical_webhook_bound_identity_without_downgrading_state(
    db_session, verified_user, payment_state
):
    from app.db.models import CreditPurchase, PaymentCheckoutDispatch
    from app.payments.checkout_outbox import (
        claim_checkout_dispatch,
        create_or_resume_checkout,
        finalize_checkout_dispatch,
    )
    from app.payments.states import payment_state_values

    created = await create_or_resume_checkout(
        verified_user,
        "starter",
        "stripe",
        db_session,
        attempt_inline=False,
    )
    claim = await claim_checkout_dispatch(db_session, created.dispatch_id)
    assert claim is not None
    await db_session.execute(
        update(CreditPurchase)
        .where(CreditPurchase.id == created.purchase_id)
        .values(mp_preference_id=STRIPE_CHECKOUT_ID, **payment_state_values(payment_state))
    )
    await db_session.commit()

    assert await finalize_checkout_dispatch(db_session, claim, _provider_checkout("stripe")) is True
    purchase = await db_session.get(CreditPurchase, created.purchase_id, populate_existing=True)
    dispatch = await db_session.get(PaymentCheckoutDispatch, created.dispatch_id, populate_existing=True)
    assert purchase.payment_state == payment_state
    assert dispatch.state == "ready"
    assert dispatch.provider_checkout_id == STRIPE_CHECKOUT_ID


@pytest.mark.asyncio
async def test_corrupt_frozen_payload_hash_blocks_provider_and_voids_purchase(db_session, verified_user):
    from app.db.models import CreditPurchase, PaymentCheckoutDispatch
    from app.payments.checkout_outbox import create_or_resume_checkout, dispatch_checkout

    created = await create_or_resume_checkout(
        verified_user,
        "starter",
        "stripe",
        db_session,
        attempt_inline=False,
    )
    dispatch = await db_session.get(PaymentCheckoutDispatch, created.dispatch_id)
    dispatch.request_payload = dispatch.request_payload.replace("starter", "popular")
    await db_session.commit()
    calls = 0

    async def provider(_claim):
        nonlocal calls
        calls += 1
        return _provider_checkout("stripe")

    failed = await dispatch_checkout(db_session, created.dispatch_id, provider_call=provider)
    assert failed.state == "failed"
    assert calls == 0
    assert (await db_session.get(CreditPurchase, created.purchase_id, populate_existing=True)).payment_state == "void"


@pytest.mark.asyncio
async def test_terminal_purchase_before_claim_cancels_without_provider_call(db_session, verified_user):
    from app.db.models import CreditPurchase, PaymentCheckoutDispatch
    from app.payments.checkout_outbox import create_or_resume_checkout, dispatch_checkout
    from app.payments.states import payment_state_values

    created = await create_or_resume_checkout(
        verified_user,
        "starter",
        "stripe",
        db_session,
        attempt_inline=False,
    )
    await db_session.execute(
        update(CreditPurchase).where(CreditPurchase.id == created.purchase_id).values(**payment_state_values("void"))
    )
    await db_session.commit()
    calls = 0

    async def provider(_claim):
        nonlocal calls
        calls += 1
        return _provider_checkout("stripe")

    cancelled = await dispatch_checkout(db_session, created.dispatch_id, provider_call=provider)
    assert cancelled.state == "cancelled"
    assert calls == 0
    dispatch = await db_session.get(PaymentCheckoutDispatch, created.dispatch_id, populate_existing=True)
    assert dispatch.error_code == "purchase_terminal"


@pytest.mark.asyncio
async def test_client_request_key_replays_ready_conflicts_on_payload_and_is_owner_scoped(
    db_session, verified_user, other_verified_user
):
    from app.payments.checkout_outbox import CheckoutIdempotencyConflict, create_or_resume_checkout

    calls = 0

    async def provider(claim):
        nonlocal calls
        calls += 1
        return _provider_checkout(claim.provider, suffix=str(calls))

    first = await create_or_resume_checkout(
        verified_user,
        "starter",
        "stripe",
        db_session,
        request_key="client-attempt-1",
        provider_call=provider,
    )
    replay = await create_or_resume_checkout(
        verified_user,
        "starter",
        "stripe",
        db_session,
        request_key="client-attempt-1",
        provider_call=provider,
    )
    assert replay == first
    assert calls == 1

    with pytest.raises(CheckoutIdempotencyConflict):
        await create_or_resume_checkout(
            verified_user,
            "popular",
            "stripe",
            db_session,
            request_key="client-attempt-1",
            provider_call=provider,
        )

    other = await create_or_resume_checkout(
        other_verified_user,
        "starter",
        "stripe",
        db_session,
        request_key="client-attempt-1",
        provider_call=provider,
    )
    assert other.purchase_id != first.purchase_id
    assert calls == 2


@pytest.mark.asyncio
async def test_replay_uses_frozen_payload_after_catalog_settings_and_user_change(
    db_session, verified_user, monkeypatch
):
    from app.config import settings
    from app.db.models import PaymentCheckoutDispatch
    from app.payments.checkout_outbox import create_or_resume_checkout, dispatch_checkout
    from app.payments.schemas import CREDIT_PACKAGES

    created = await create_or_resume_checkout(
        verified_user,
        "starter",
        "stripe",
        db_session,
        request_key="frozen-request",
        attempt_inline=False,
    )
    dispatch = await db_session.get(PaymentCheckoutDispatch, created.dispatch_id)
    frozen = (dispatch.request_payload, dispatch.request_payload_hash)

    monkeypatch.delitem(CREDIT_PACKAGES, "starter")
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://changed.example")
    monkeypatch.setattr(settings, "BACKEND_URL", "https://changed-backend.example")
    verified_user.email = "changed@example.com"
    seen = []

    async def provider(claim):
        seen.append((claim.request_payload, claim.request_payload_hash))
        return _provider_checkout("stripe")

    ready = await dispatch_checkout(db_session, created.dispatch_id, provider_call=provider)
    replay = await create_or_resume_checkout(
        verified_user,
        "starter",
        "stripe",
        db_session,
        request_key="frozen-request",
        provider_call=provider,
    )
    assert ready == replay
    assert seen == [frozen]


@pytest.mark.asyncio
async def test_checkout_http_ready_preserves_exact_legacy_body_and_replays_same_url(
    client, verified_user, auth_headers, monkeypatch
):
    provider_calls = 0

    class Preference:
        @staticmethod
        def create(_payload, request_options=None):
            nonlocal provider_calls
            provider_calls += 1
            return {
                "status": 201,
                "response": {"id": MP_CHECKOUT_ID, "init_point": MP_CHECKOUT_URL},
            }

    class SDK:
        @staticmethod
        def preference():
            return Preference()

    monkeypatch.setattr("app.payments.service._get_sdk", lambda: SDK())
    headers = {**auth_headers(verified_user), "Idempotency-Key": "http-ready-1"}
    first = await client.post(
        "/api/v1/credits/checkout",
        json={"package": "starter", "provider": "mercadopago"},
        headers=headers,
    )
    replay = await client.post(
        "/api/v1/credits/checkout",
        json={"package": "starter", "provider": "mercadopago"},
        headers=headers,
    )

    assert first.status_code == replay.status_code == 200
    assert first.json() == replay.json()
    assert set(first.json()) == {"checkout_url", "purchase_id"}
    assert first.json()["checkout_url"] == MP_CHECKOUT_URL
    assert provider_calls == 1


@pytest.mark.asyncio
async def test_checkout_http_pending_replay_conflict_and_owner_only_poll(
    client,
    verified_user,
    other_verified_user,
    auth_headers,
    monkeypatch,
):
    provider_calls = 0

    class Preference:
        @staticmethod
        def create(_payload, request_options=None):
            nonlocal provider_calls
            provider_calls += 1
            raise RuntimeError("ambiguous connection reset")

    class SDK:
        @staticmethod
        def preference():
            return Preference()

    monkeypatch.setattr("app.payments.service._get_sdk", lambda: SDK())
    headers = {**auth_headers(verified_user), "Idempotency-Key": "http-pending-1"}
    first = await client.post(
        "/api/v1/credits/checkout",
        json={"package": "starter", "provider": "mercadopago"},
        headers=headers,
    )
    replay = await client.post(
        "/api/v1/credits/checkout",
        json={"package": "starter", "provider": "mercadopago"},
        headers=headers,
    )

    assert first.status_code == replay.status_code == 202
    assert first.json() == replay.json()
    assert set(first.json()) == {"dispatch_id", "purchase_id", "state"}
    assert first.json()["state"] == "pending"
    assert provider_calls == 1

    purchase_id = first.json()["purchase_id"]
    owner = await client.get(
        f"/api/v1/credits/checkout/{purchase_id}",
        headers=auth_headers(verified_user),
    )
    other = await client.get(
        f"/api/v1/credits/checkout/{purchase_id}",
        headers=auth_headers(other_verified_user),
    )
    missing = await client.get(
        f"/api/v1/credits/checkout/{uuid.uuid4()}",
        headers=auth_headers(verified_user),
    )
    assert owner.status_code == 200
    assert owner.json() == first.json()
    assert other.status_code == missing.status_code == 404
    assert other.json() == missing.json()

    conflict = await client.post(
        "/api/v1/credits/checkout",
        json={"package": "popular", "provider": "mercadopago"},
        headers=headers,
    )
    assert conflict.status_code == 409
    assert provider_calls == 1


def test_checkout_reconciler_is_callable_and_wired_to_conservative_beat(monkeypatch):
    from app.worker import tasks
    from app.worker.celery_app import celery_app

    calls = 0

    async def fake_reconcile():
        nonlocal calls
        calls += 1
        return {"ready": 1, "pending": 2, "failed": 0, "cancelled": 0}

    monkeypatch.setattr(tasks, "_reconcile_payment_checkout_dispatches_async", fake_reconcile)
    assert calls == 0
    assert tasks.reconcile_payment_checkout_dispatches() == {
        "ready": 1,
        "pending": 2,
        "failed": 0,
        "cancelled": 0,
    }
    assert calls == 1
    entry = celery_app.conf.beat_schedule["reconcile-payment-checkout-dispatches"]
    assert entry["task"] == "reconcile_payment_checkout_dispatches"
    assert timedelta(minutes=1) <= entry["schedule"] <= timedelta(minutes=10)
