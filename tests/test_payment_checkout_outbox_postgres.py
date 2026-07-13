from __future__ import annotations

import asyncio
import os
import re
import uuid
from datetime import datetime, timedelta, timezone

import asyncpg
import pytest
import pytest_asyncio
import stripe
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import CreditPurchase, PaymentCheckoutDispatch, ProcessedPaymentEvent, User
from app.payments.checkout_outbox import (
    ProviderCheckout,
    _schedule_retry,
    _terminalize_claim,
    claim_checkout_dispatch,
    create_or_resume_checkout,
    dispatch_checkout,
    finalize_checkout_dispatch,
    reconcile_checkout_dispatches,
)
from app.payments.service import process_webhook_stripe
from app.payments.snapshot import build_snapshot_metadata
from app.payments.states import payment_state_values

_ADMIN_DSN = os.getenv(
    "POSTGRES_PAYMENT_TEST_ADMIN_DSN",
    "postgresql://clipia:clipia_dev@localhost:5435/postgres",
)
_CHECKOUT_ID = "cs_test_1234567890abcdef12345678"
_CHECKOUT_URL = f"https://checkout.stripe.com/c/pay/{_CHECKOUT_ID}"


def _require_postgres_tests() -> None:
    if os.getenv("RUN_POSTGRES_PAYMENT_TESTS") != "1":
        pytest.skip("set RUN_POSTGRES_PAYMENT_TESTS=1 to run real PostgreSQL checkout outbox tests")


@pytest_asyncio.fixture
async def postgres_checkout_sessions():
    _require_postgres_tests()
    database_name = f"clipia_checkout_test_{uuid.uuid4().hex[:12]}"
    assert re.fullmatch(r"clipia_checkout_test_[0-9a-f]{12}", database_name)
    admin = await asyncpg.connect(_ADMIN_DSN)
    await admin.execute(f'CREATE DATABASE "{database_name}"')
    database_url = f"postgresql+asyncpg://clipia:clipia_dev@localhost:5435/{database_name}"
    engine = create_async_engine(database_url, pool_size=10, max_overflow=10)
    sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        yield sessions
    finally:
        await engine.dispose()
        await admin.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = $1 AND pid <> pg_backend_pid()",
            database_name,
        )
        await admin.execute(f'DROP DATABASE "{database_name}"')
        await admin.close()


async def _seed_pending(sessions, *, provider: str = "stripe", request_key: str | None = None):
    async with sessions() as db:
        user = User(
            id=uuid.uuid4(),
            email=f"checkout-{uuid.uuid4().hex}@example.com",
            name="Checkout PG",
            password_hash="test",
            credits=5,
            email_verified=True,
            referral_code=uuid.uuid4().hex[:8],
        )
        db.add(user)
        await db.commit()
        outcome = await create_or_resume_checkout(
            user,
            "starter",
            provider,
            db,
            request_key=request_key,
            attempt_inline=False,
        )
        return user, outcome


@pytest.mark.asyncio
async def test_postgres_skip_locked_two_claimers_make_exactly_one_provider_call_without_network_lock(
    postgres_checkout_sessions,
):
    sessions = postgres_checkout_sessions
    _user, created = await _seed_pending(sessions)

    async with sessions() as holder:
        await holder.execute(
            select(PaymentCheckoutDispatch).where(PaymentCheckoutDispatch.id == created.dispatch_id).with_for_update()
        )
        async with sessions() as skipped:
            assert (
                await asyncio.wait_for(
                    claim_checkout_dispatch(skipped, created.dispatch_id),
                    timeout=1,
                )
                is None
            )
        await holder.rollback()

    provider_started = asyncio.Event()
    provider_release = asyncio.Event()
    calls = []

    async def provider(claim):
        calls.append(claim.publisher_token)
        async with sessions() as lock_probe:
            await lock_probe.execute(
                select(PaymentCheckoutDispatch)
                .where(PaymentCheckoutDispatch.id == claim.dispatch_id)
                .with_for_update(nowait=True)
            )
            await lock_probe.rollback()
        provider_started.set()
        await provider_release.wait()
        return ProviderCheckout(_CHECKOUT_ID, _CHECKOUT_URL)

    async def attempt():
        async with sessions() as db:
            return await dispatch_checkout(db, created.dispatch_id, provider_call=provider)

    winner = asyncio.create_task(attempt())
    await asyncio.wait_for(provider_started.wait(), timeout=2)
    loser = await attempt()
    provider_release.set()
    winner_result = await winner

    assert len(calls) == 1
    assert {loser.state, winner_result.state} <= {"pending", "ready"}
    async with sessions() as verify:
        dispatch = await verify.get(PaymentCheckoutDispatch, created.dispatch_id)
        assert dispatch.state == "ready"
        assert dispatch.publisher_token is None


@pytest.mark.asyncio
async def test_postgres_concurrent_same_client_key_creates_one_purchase_and_provider_call(
    postgres_checkout_sessions,
):
    sessions = postgres_checkout_sessions
    user, _unused = await _seed_pending(sessions)
    # The helper's first row intentionally has no key; only the concurrent pair shares this key.
    provider_started = asyncio.Event()
    provider_release = asyncio.Event()
    calls = 0

    async def provider(_claim):
        nonlocal calls
        calls += 1
        provider_started.set()
        await provider_release.wait()
        return ProviderCheckout(_CHECKOUT_ID, _CHECKOUT_URL)

    async def create_same_key():
        async with sessions() as db:
            return await create_or_resume_checkout(
                user,
                "starter",
                "stripe",
                db,
                request_key="postgres-same-request",
                provider_call=provider,
            )

    first = asyncio.create_task(create_same_key())
    second = asyncio.create_task(create_same_key())
    await asyncio.wait_for(provider_started.wait(), timeout=3)
    provider_release.set()
    first_result, second_result = await asyncio.gather(first, second)
    replay = await create_same_key()

    assert first_result.purchase_id == second_result.purchase_id == replay.purchase_id
    assert replay.state == "ready"
    assert calls == 1
    async with sessions() as verify:
        assert (
            await verify.scalar(
                select(func.count())
                .select_from(PaymentCheckoutDispatch)
                .where(PaymentCheckoutDispatch.request_key.is_not(None))
            )
            == 1
        )


@pytest.mark.asyncio
async def test_postgres_provider_accepts_then_process_death_replays_same_request_and_binds_once(
    postgres_checkout_sessions,
):
    sessions = postgres_checkout_sessions
    _user, created = await _seed_pending(sessions)

    class ProcessDeath(BaseException):
        pass

    seen = []

    async def accepted_then_dies(claim):
        seen.append((claim.provider_idempotency_key, claim.request_payload))
        raise ProcessDeath

    async with sessions() as db:
        with pytest.raises(ProcessDeath):
            await dispatch_checkout(db, created.dispatch_id, provider_call=accepted_then_dies)

    async with sessions() as expire:
        await expire.execute(
            update(PaymentCheckoutDispatch)
            .where(PaymentCheckoutDispatch.id == created.dispatch_id)
            .values(publisher_lease_until=datetime.now(timezone.utc) - timedelta(seconds=1))
        )
        await expire.commit()

    async def replay_provider(claim):
        seen.append((claim.provider_idempotency_key, claim.request_payload))
        return ProviderCheckout(_CHECKOUT_ID, _CHECKOUT_URL)

    async with sessions() as retry:
        result = await dispatch_checkout(retry, created.dispatch_id, provider_call=replay_provider)
    assert result.state == "ready"
    assert seen[0] == seen[1]
    async with sessions() as verify:
        dispatch = await verify.get(PaymentCheckoutDispatch, created.dispatch_id)
        purchase = await verify.get(CreditPurchase, created.purchase_id)
        assert dispatch.provider_checkout_id == purchase.mp_preference_id == _CHECKOUT_ID


@pytest.mark.asyncio
async def test_postgres_binding_commit_failure_stays_pending_then_converges(
    postgres_checkout_sessions,
    monkeypatch,
):
    sessions = postgres_checkout_sessions
    _user, created = await _seed_pending(sessions)
    seen = []

    async def provider(claim):
        seen.append((claim.provider_idempotency_key, claim.request_payload))
        return ProviderCheckout(_CHECKOUT_ID, _CHECKOUT_URL)

    async with sessions() as db:
        real_commit = db.commit
        commit_calls = 0

        async def fail_binding_once():
            nonlocal commit_calls
            commit_calls += 1
            if commit_calls == 2:
                raise RuntimeError("simulated commit loss after provider")
            await real_commit()

        monkeypatch.setattr(db, "commit", fail_binding_once)
        pending = await dispatch_checkout(db, created.dispatch_id, provider_call=provider)
        assert pending.state == "pending"

    async with sessions() as due:
        await due.execute(
            update(PaymentCheckoutDispatch)
            .where(PaymentCheckoutDispatch.id == created.dispatch_id)
            .values(next_attempt_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        )
        await due.commit()
    async with sessions() as retry:
        ready = await dispatch_checkout(retry, created.dispatch_id, provider_call=provider)
    assert ready.state == "ready"
    assert seen[0] == seen[1]


@pytest.mark.asyncio
async def test_postgres_webhook_paid_refund_and_finalizer_race_converges_identity_and_balance(
    postgres_checkout_sessions,
    monkeypatch,
):
    sessions = postgres_checkout_sessions
    user, created = await _seed_pending(sessions)
    async with sessions() as claim_session:
        claim = await claim_checkout_dispatch(claim_session, created.dispatch_id)
    assert claim is not None

    async with sessions() as load:
        purchase = await load.get(CreditPurchase, created.purchase_id)
        metadata = build_snapshot_metadata(purchase)
    payment_intent = f"pi_{uuid.uuid4().hex}"
    paid_event = {
        "id": f"evt_{uuid.uuid4().hex}",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": _CHECKOUT_ID,
                "payment_status": "paid",
                "client_reference_id": str(created.purchase_id),
                "metadata": metadata,
                "amount_total": 1990,
                "currency": "brl",
                "payment_intent": payment_intent,
            }
        },
    }
    refund_event = {
        "id": f"evt_{uuid.uuid4().hex}",
        "type": "charge.refunded",
        "data": {
            "object": {
                "id": f"ch_{uuid.uuid4().hex}",
                "payment_intent": payment_intent,
                "amount": 1990,
                "amount_refunded": 1990,
                "currency": "brl",
                "refunded": True,
            }
        },
    }
    monkeypatch.setattr(
        stripe.PaymentIntent,
        "retrieve",
        staticmethod(lambda value: {"id": value, "metadata": metadata}),
    )

    async def finalize():
        async with sessions() as db:
            return await finalize_checkout_dispatch(
                db,
                claim,
                ProviderCheckout(_CHECKOUT_ID, _CHECKOUT_URL),
            )

    async def webhook(event):
        async with sessions() as db:
            return await process_webhook_stripe(event, db)

    finalized, paid, refunded = await asyncio.gather(
        finalize(),
        webhook(paid_event),
        webhook(refund_event),
    )
    assert finalized is True
    assert paid.balance_delta + refunded.balance_delta == 0
    async with sessions() as verify:
        dispatch = await verify.get(PaymentCheckoutDispatch, created.dispatch_id)
        purchase = await verify.get(CreditPurchase, created.purchase_id)
        refreshed_user = await verify.get(User, user.id)
        assert dispatch.state == "ready"
        assert dispatch.provider_checkout_id == purchase.mp_preference_id == _CHECKOUT_ID
        assert purchase.payment_state == "refunded"
        assert refreshed_user.credits == 5
        assert (
            await verify.scalar(
                select(func.count())
                .select_from(ProcessedPaymentEvent)
                .where(ProcessedPaymentEvent.purchase_id == created.purchase_id)
            )
            == 2
        )


@pytest.mark.asyncio
async def test_postgres_expired_publisher_cannot_mutate_reclaimed_dispatch(postgres_checkout_sessions):
    sessions = postgres_checkout_sessions
    _user, created = await _seed_pending(sessions)
    claimed_at = datetime.now(timezone.utc)
    async with sessions() as first_session:
        first = await claim_checkout_dispatch(
            first_session,
            created.dispatch_id,
            now=claimed_at,
            lease_duration=timedelta(seconds=1),
        )
    assert first is not None

    async with sessions() as second_session:
        second = await claim_checkout_dispatch(
            second_session,
            created.dispatch_id,
            now=claimed_at + timedelta(seconds=2),
        )
    assert second is not None
    assert second.publisher_token != first.publisher_token

    async with sessions() as stale_retry:
        assert (
            await _schedule_retry(
                stale_retry,
                first,
                code="provider_unavailable",
                detail="stale retry",
                now=claimed_at + timedelta(seconds=3),
            )
            is False
        )
    async with sessions() as stale_terminal:
        assert (
            await _terminalize_claim(
                stale_terminal,
                first,
                state="failed",
                code="provider_rejected",
                detail="stale terminalizer",
                now=claimed_at + timedelta(seconds=3),
            )
            is False
        )
    async with sessions() as verify:
        persisted = await verify.get(PaymentCheckoutDispatch, created.dispatch_id)
        assert persisted.state == "pending"
        assert persisted.publisher_token == second.publisher_token


@pytest.mark.asyncio
async def test_postgres_reconciler_consumes_poison_and_terminal_rows_before_valid_due_row(
    postgres_checkout_sessions,
):
    sessions = postgres_checkout_sessions
    _poison_user, poison = await _seed_pending(sessions)
    _paid_user, paid = await _seed_pending(sessions)
    _valid_user, valid = await _seed_pending(sessions)
    due = datetime.now(timezone.utc)
    async with sessions() as prepare:
        poison_dispatch = await prepare.get(PaymentCheckoutDispatch, poison.dispatch_id)
        poison_dispatch.request_payload = poison_dispatch.request_payload.replace("starter", "tampered")
        poison_dispatch.next_attempt_at = due - timedelta(seconds=3)
        paid_dispatch = await prepare.get(PaymentCheckoutDispatch, paid.dispatch_id)
        paid_dispatch.next_attempt_at = due - timedelta(seconds=2)
        valid_dispatch = await prepare.get(PaymentCheckoutDispatch, valid.dispatch_id)
        valid_dispatch.next_attempt_at = due - timedelta(seconds=1)
        await prepare.execute(
            update(CreditPurchase).where(CreditPurchase.id == paid.purchase_id).values(**payment_state_values("paid"))
        )
        await prepare.commit()
    provider_calls = 0

    async def provider(_claim):
        nonlocal provider_calls
        provider_calls += 1
        checkout_id = f"{_CHECKOUT_ID}{provider_calls}"
        return ProviderCheckout(checkout_id, f"https://checkout.stripe.com/c/pay/{checkout_id}")

    counts = await reconcile_checkout_dispatches(sessions, limit=3, provider_call=provider)

    assert counts == {"ready": 1, "pending": 0, "failed": 1, "cancelled": 1}
    assert provider_calls == 1
    async with sessions() as verify:
        assert (await verify.get(CreditPurchase, poison.purchase_id)).payment_state == "void"
        assert (await verify.get(CreditPurchase, paid.purchase_id)).payment_state == "paid"
        assert (await verify.get(PaymentCheckoutDispatch, valid.dispatch_id)).state == "ready"
