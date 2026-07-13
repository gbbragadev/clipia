import asyncio
import os
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import asyncpg
import pytest
import pytest_asyncio
import stripe
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app import observability
from app.api.routes import _debit_credits, admin_adjust_credits
from app.auth.referrals import award_verified_referral
from app.db.base import Base
from app.db.models import (
    CreditAdjustment,
    CreditPurchase,
    Job,
    JobDispatch,
    ProcessedPaymentEvent,
    ReferralCreditAward,
    User,
)
from app.models import AdminCreditAdjustRequest
from app.payments.service import _apply_payment_event, process_webhook_stripe

_ADMIN_DSN = os.getenv(
    "POSTGRES_PAYMENT_TEST_ADMIN_DSN",
    "postgresql://clipia:clipia_dev@localhost:5435/postgres",
)


def _require_postgres_tests() -> None:
    if os.getenv("RUN_POSTGRES_PAYMENT_TESTS") != "1":
        pytest.skip("set RUN_POSTGRES_PAYMENT_TESTS=1 to run real PostgreSQL payment races")


@pytest_asyncio.fixture
async def postgres_payment_sessions():
    _require_postgres_tests()
    database_name = f"clipia_payment_test_{uuid.uuid4().hex[:12]}"
    assert re.fullmatch(r"clipia_payment_test_[0-9a-f]{12}", database_name)
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


@pytest.fixture(autouse=True)
def _disable_process_local_payment_lock(monkeypatch):
    @asynccontextmanager
    async def no_process_lock():
        yield

    monkeypatch.setattr("app.payments.service.get_lock", lambda _key: no_process_lock())


async def _seed_user(sessions, *, credits: int = 5) -> User:
    async with sessions() as session:
        user = User(
            id=uuid.uuid4(),
            email=f"postgres-payment-{uuid.uuid4().hex}@example.com",
            name="PostgreSQL Payment Test",
            password_hash="test",
            credits=credits,
            email_verified=True,
            referral_code=uuid.uuid4().hex[:8],
        )
        session.add(user)
        await session.commit()
        return user


async def _seed_purchase(
    sessions,
    user: User,
    *,
    checkout_id: str,
    status: str = "pending",
    payment_state: str | None = "pending",
) -> CreditPurchase:
    async with sessions() as session:
        purchase = CreditPurchase(
            id=uuid.uuid4(),
            user_id=user.id,
            package_name="starter",
            credits_amount=10,
            bonus_credits=0,
            price_brl=1990,
            currency="BRL",
            provider="stripe",
            mp_preference_id=checkout_id,
            status=status,
            payment_state=payment_state,
        )
        session.add(purchase)
        await session.commit()
        return purchase


@pytest.mark.asyncio
async def test_postgres_admin_beta_adjustment_racing_payment_and_generation_has_no_lost_update(
    postgres_payment_sessions,
):
    sessions = postgres_payment_sessions
    user = await _seed_user(sessions, credits=20)
    admin = await _seed_user(sessions, credits=0)
    purchase = await _seed_purchase(sessions, user, checkout_id=f"checkout_{uuid.uuid4().hex}")

    async def adjust_beta():
        async with sessions() as session:
            return await admin_adjust_credits(
                str(user.id),
                AdminCreditAdjustRequest(delta=18, reason="beta_invite_2026"),
                admin,
                session,
            )

    async def credit_payment():
        async with sessions() as session:
            return await _apply_payment_event(
                session,
                purchase_id=purchase.id,
                provider="stripe",
                event_key=f"evt_{uuid.uuid4().hex}",
                event_type="checkout.session.completed",
                transition="paid",
                external_payment_id=f"pi_{uuid.uuid4().hex}",
                external_checkout_id=purchase.mp_preference_id,
                validate=lambda _purchase: True,
            )

    async def debit_generation():
        async with sessions() as session:
            await _debit_credits(session, user.id, 3)

    adjustment, payment, _debit = await asyncio.gather(adjust_beta(), credit_payment(), debit_generation())

    assert adjustment["delta"] == 18
    assert payment.applied is True
    async with sessions() as verification:
        assert (await verification.get(User, user.id)).credits == 45
        adjustments = (
            (await verification.execute(select(CreditAdjustment).where(CreditAdjustment.target_user_id == user.id)))
            .scalars()
            .all()
        )
        assert len(adjustments) == 1
        assert adjustments[0].delta == 18
        assert adjustments[0].reason == "beta_invite_2026"


@pytest.mark.asyncio
async def test_postgres_referral_limit_is_serialized_under_concurrent_verifications(
    postgres_payment_sessions,
):
    sessions = postgres_payment_sessions
    referrer = await _seed_user(sessions, credits=18)
    referred_users = [await _seed_user(sessions, credits=2) for _ in range(11)]
    async with sessions() as seed_session:
        await seed_session.execute(
            User.__table__.update()
            .where(User.id.in_([user.id for user in referred_users]))
            .values(referred_by=referrer.id)
        )
        seed_session.add_all(
            [
                ReferralCreditAward(
                    referred_user_id=user.id,
                    referrer_user_id=referrer.id,
                    credits=2,
                )
                for user in referred_users[:9]
            ]
        )
        await seed_session.commit()

    async def award(user_id):
        async with sessions() as session:
            referred = await session.get(User, user_id)
            result = await award_verified_referral(session, referred)
            await session.commit()
            return result

    results = await asyncio.gather(award(referred_users[9].id), award(referred_users[10].id))

    assert sorted(results) == [0, 2]
    async with sessions() as verification:
        assert await verification.scalar(select(func.count()).select_from(ReferralCreditAward)) == 10
        assert (await verification.get(User, referrer.id)).credits == 20


def _paid_event(purchase: CreditPurchase, *, event_id: str, payment_intent: str) -> dict:
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": purchase.mp_preference_id,
                "payment_status": "paid",
                "client_reference_id": str(purchase.id),
                "metadata": {"purchase_id": str(purchase.id)},
                "amount_total": purchase.price_brl,
                "currency": "brl",
                "payment_intent": payment_intent,
            }
        },
    }


def _refund_event(purchase: CreditPurchase, *, event_id: str, payment_intent: str) -> dict:
    return {
        "id": event_id,
        "type": "charge.refunded",
        "data": {
            "object": {
                "id": f"ch_{event_id}",
                "payment_intent": payment_intent,
                "amount": purchase.price_brl,
                "amount_refunded": purchase.price_brl,
                "currency": "brl",
                "refunded": True,
            }
        },
    }


async def _apply_event(sessions, event: dict) -> bool:
    async with sessions() as session:
        return await process_webhook_stripe(event, session)


@pytest.mark.asyncio
async def test_postgres_paid_and_refund_race_converges_to_refunded_without_credit_loss(
    postgres_payment_sessions, monkeypatch
):
    sessions = postgres_payment_sessions
    user = await _seed_user(sessions)
    purchase = await _seed_purchase(sessions, user, checkout_id=f"cs_{uuid.uuid4().hex}")
    payment_intent = f"pi_{uuid.uuid4().hex}"
    monkeypatch.setattr(
        stripe.PaymentIntent,
        "retrieve",
        staticmethod(
            lambda pi: {
                "id": pi,
                "metadata": {"purchase_id": str(purchase.id)},
            }
        ),
    )

    await asyncio.gather(
        _apply_event(
            sessions, _paid_event(purchase, event_id=f"evt_{uuid.uuid4().hex}", payment_intent=payment_intent)
        ),
        _apply_event(
            sessions,
            _refund_event(purchase, event_id=f"evt_{uuid.uuid4().hex}", payment_intent=payment_intent),
        ),
    )

    async with sessions() as session:
        assert (await session.get(CreditPurchase, purchase.id)).payment_state == "refunded"
        assert (await session.get(User, user.id)).credits == 5
        assert (
            await session.scalar(
                select(func.count())
                .select_from(ProcessedPaymentEvent)
                .where(ProcessedPaymentEvent.purchase_id == purchase.id)
            )
            == 2
        )


@pytest.mark.asyncio
async def test_postgres_two_purchase_credits_and_generation_debit_preserve_arithmetic_sum(
    postgres_payment_sessions,
):
    sessions = postgres_payment_sessions
    user = await _seed_user(sessions)
    first = await _seed_purchase(sessions, user, checkout_id=f"cs_{uuid.uuid4().hex}")
    second = await _seed_purchase(sessions, user, checkout_id=f"cs_{uuid.uuid4().hex}")

    async def debit_generation():
        async with sessions() as session:
            await _debit_credits(session, user.id, 3)

    results = await asyncio.gather(
        _apply_event(
            sessions,
            _paid_event(first, event_id=f"evt_{uuid.uuid4().hex}", payment_intent=f"pi_{uuid.uuid4().hex}"),
        ),
        _apply_event(
            sessions,
            _paid_event(second, event_id=f"evt_{uuid.uuid4().hex}", payment_intent=f"pi_{uuid.uuid4().hex}"),
        ),
        debit_generation(),
    )

    assert [result.applied for result in results[:2]] == [True, True]
    async with sessions() as session:
        assert (await session.get(User, user.id)).credits == 22


@pytest.mark.asyncio
async def test_postgres_concurrent_replay_claims_once(postgres_payment_sessions):
    sessions = postgres_payment_sessions
    user = await _seed_user(sessions)
    purchase = await _seed_purchase(sessions, user, checkout_id=f"cs_{uuid.uuid4().hex}")
    event = _paid_event(
        purchase,
        event_id=f"evt_{uuid.uuid4().hex}",
        payment_intent=f"pi_{uuid.uuid4().hex}",
    )

    results = await asyncio.gather(_apply_event(sessions, event), _apply_event(sessions, event))

    assert sorted(result.applied for result in results) == [False, True]
    async with sessions() as session:
        assert (await session.get(User, user.id)).credits == 15
        assert (
            await session.scalar(
                select(func.count())
                .select_from(ProcessedPaymentEvent)
                .where(ProcessedPaymentEvent.purchase_id == purchase.id)
            )
            == 1
        )


@pytest.mark.asyncio
async def test_postgres_provider_identity_collision_credits_only_one_purchase(postgres_payment_sessions):
    sessions = postgres_payment_sessions
    user = await _seed_user(sessions)
    first = await _seed_purchase(sessions, user, checkout_id=f"cs_{uuid.uuid4().hex}")
    second = await _seed_purchase(sessions, user, checkout_id=f"cs_{uuid.uuid4().hex}")
    payment_intent = f"pi_{uuid.uuid4().hex}"

    results = await asyncio.gather(
        _apply_event(
            sessions,
            _paid_event(first, event_id=f"evt_{uuid.uuid4().hex}", payment_intent=payment_intent),
        ),
        _apply_event(
            sessions,
            _paid_event(second, event_id=f"evt_{uuid.uuid4().hex}", payment_intent=payment_intent),
        ),
    )

    assert sorted(result.applied for result in results) == [False, True]
    async with sessions() as session:
        purchases = list(
            (await session.scalars(select(CreditPurchase).where(CreditPurchase.id.in_([first.id, second.id])))).all()
        )
        assert sorted(purchase.payment_state for purchase in purchases) == ["paid", "pending"]
        assert (await session.get(User, user.id)).credits == 15
        assert (
            await session.scalar(
                select(func.count())
                .select_from(ProcessedPaymentEvent)
                .where(ProcessedPaymentEvent.purchase_id.in_([first.id, second.id]))
            )
            == 1
        )


@pytest.mark.asyncio
async def test_postgres_authoritative_aggregates_respect_rolling_payment_precedence(
    postgres_payment_sessions,
    monkeypatch,
):
    sessions = postgres_payment_sessions
    user = await _seed_user(sessions)
    refunded = await _seed_purchase(
        sessions,
        user,
        checkout_id=f"cs_{uuid.uuid4().hex}",
        status="approved",
        payment_state="refunded",
    )
    paid = await _seed_purchase(
        sessions,
        user,
        checkout_id=f"cs_{uuid.uuid4().hex}",
        status="pending",
        payment_state="paid",
    )
    async with sessions() as session:
        paid.bonus_credits = 2
        paid.paid_at = datetime.now(timezone.utc)
        refunded.paid_at = datetime.now(timezone.utc)
        session.add_all([paid, refunded])
        job = Job(
            user_id=user.id,
            topic="PostgreSQL aggregate",
            style="educational",
            duration_target=45,
            status="editable",
        )
        session.add(job)
        await session.flush()
        session.add(
            JobDispatch(
                job_id=job.id,
                operation_id=job.id,
                kind="generation",
                payload={},
                debited_credits=3,
                state="completed",
            )
        )
        await session.commit()

    @asynccontextmanager
    async def runtime_session():
        async with sessions() as session:
            yield session

    monkeypatch.setattr(observability, "_runtime_session", runtime_session)

    assert await observability._get_credit_totals() == {"purchased": 12.0, "consumed": 3.0}
