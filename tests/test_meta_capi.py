from __future__ import annotations

import importlib.util
import json
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from typing import Protocol

import pytest
from httpx import AsyncClient
from pydantic import SecretStr
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, settings
from app.db.base import Base
from app.db.models import CreditPurchase, MetaConversionOutbox, User
from app.marketing import meta_capi


class _PurchaseFactory(Protocol):
    def __call__(self, *, provider: str, snapshot: bool) -> Awaitable[CreditPurchase]: ...


def test_meta_capi_defaults_off_and_outbox_has_durable_retry_fields() -> None:
    configured = Settings(_env_file=None)
    assert configured.META_CAPI_ENABLED is False

    assert "meta_conversion_outbox" in Base.metadata.tables
    columns = Base.metadata.tables["meta_conversion_outbox"].c
    assert {
        "event_id",
        "user_id",
        "event_name",
        "payload",
        "status",
        "attempts",
        "next_attempt_at",
        "last_attempt_at",
        "lease_token",
        "lease_until",
        "sent_at",
    }.issubset(columns.keys())
    assert columns.event_id.unique is True
    user_fk = next(iter(columns.user_id.foreign_keys))
    assert user_fk.target_fullname == "users.id"
    assert user_fk.ondelete == "CASCADE"
    status_check = next(
        constraint
        for constraint in Base.metadata.tables["meta_conversion_outbox"].constraints
        if constraint.name == "ck_meta_outbox_status"
    )
    assert "cancelled" in str(status_check.sqltext)
    assert "dispatching" in str(status_check.sqltext)


def test_meta_capi_service_module_exists() -> None:
    assert importlib.util.find_spec("app.marketing.meta_capi") is not None


def test_meta_dispatcher_is_callable_and_wired_to_conservative_beat(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.worker import tasks
    from app.worker.celery_app import celery_app

    calls = 0

    async def fake_dispatch() -> dict[str, int]:
        nonlocal calls
        calls += 1
        return {"sent": 1, "retried": 0, "failed": 0, "cancelled": 0, "unsupported": 0}

    monkeypatch.setattr(tasks, "_dispatch_meta_conversions_async", fake_dispatch, raising=False)
    assert tasks.dispatch_meta_conversions() == {
        "sent": 1,
        "retried": 0,
        "failed": 0,
        "cancelled": 0,
        "unsupported": 0,
    }
    assert calls == 1
    entry = celery_app.conf.beat_schedule["dispatch-meta-conversions"]
    assert entry["task"] == "dispatch_meta_conversions"
    assert timedelta(minutes=1) <= entry["schedule"] <= timedelta(minutes=10)


def _configure_meta(monkeypatch: pytest.MonkeyPatch, *, enabled: bool = True) -> None:
    monkeypatch.setattr(settings, "META_CAPI_ENABLED", enabled)
    monkeypatch.setattr(settings, "META_CAPI_PIXEL_ID", "pixel-123")
    monkeypatch.setattr(settings, "META_CAPI_ACCESS_TOKEN", SecretStr("meta-access-token"))
    monkeypatch.setattr(settings, "META_CAPI_API_VERSION", "v23.0")
    monkeypatch.setattr(settings, "MARKETING_PSEUDONYM_SECRET", SecretStr("pseudonym-secret-value"))


@pytest.mark.asyncio
async def test_enqueue_requires_enabled_complete_config_and_consent_and_never_stores_raw_email(
    db_session: AsyncSession, verified_user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert hasattr(meta_capi, "enqueue_meta_conversion")
    enqueue_meta_conversion = meta_capi.enqueue_meta_conversion
    verified_user.marketing_measurement_consented_at = datetime.now(timezone.utc)
    await db_session.commit()
    event_id = f"complete-registration:{verified_user.id}"

    _configure_meta(monkeypatch, enabled=False)
    assert (
        await enqueue_meta_conversion(
            db_session,
            user=verified_user,
            event_name="CompleteRegistration",
            event_id=event_id,
        )
        is False
    )
    monkeypatch.setattr(settings, "META_CAPI_ENABLED", True)
    monkeypatch.setattr(settings, "META_CAPI_ACCESS_TOKEN", SecretStr(""))
    assert (
        await enqueue_meta_conversion(
            db_session,
            user=verified_user,
            event_name="CompleteRegistration",
            event_id=event_id,
        )
        is False
    )
    monkeypatch.setattr(settings, "META_CAPI_ACCESS_TOKEN", SecretStr("meta-access-token"))
    verified_user.marketing_measurement_consented_at = None
    assert (
        await enqueue_meta_conversion(
            db_session,
            user=verified_user,
            event_name="CompleteRegistration",
            event_id=event_id,
        )
        is False
    )
    assert await db_session.scalar(select(func.count()).select_from(MetaConversionOutbox)) == 0

    verified_user.marketing_measurement_consented_at = datetime.now(timezone.utc)
    assert await enqueue_meta_conversion(
        db_session,
        user=verified_user,
        event_name="CompleteRegistration",
        event_id=event_id,
    )
    assert (
        await enqueue_meta_conversion(
            db_session,
            user=verified_user,
            event_name="CompleteRegistration",
            event_id=event_id,
        )
        is False
    )
    await db_session.commit()

    row = await db_session.scalar(select(MetaConversionOutbox))
    assert row is not None
    assert row.event_id == event_id
    assert row.user_id == verified_user.id
    assert row.event_name == "CompleteRegistration"
    serialized = json.dumps(row.payload, sort_keys=True).lower()
    assert verified_user.email.lower() not in serialized
    assert "meta-access-token" not in serialized
    assert "pseudonym-secret-value" not in serialized
    assert row.payload["user_data"]["em"][0] != verified_user.email.lower()
    assert len(row.payload["user_data"]["em"][0]) == 64
    assert len(row.payload["user_data"]["external_id"][0]) == 64


class _SuccessfulResponse:
    def raise_for_status(self) -> None:
        return None


class _RecordingClient:
    def __init__(self, *, failure: Exception | None = None) -> None:
        self.failure = failure
        self.calls: list[dict[str, object]] = []

    async def post(
        self, url: str, *, json: dict[str, object], headers: dict[str, str], timeout: float
    ) -> _SuccessfulResponse:
        self.calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        if self.failure is not None:
            raise self.failure
        return _SuccessfulResponse()


@pytest.mark.asyncio
async def test_dispatch_is_disabled_without_config_and_sqlite_is_explicitly_unsupported_without_network(
    db_session: AsyncSession, verified_user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert hasattr(meta_capi, "dispatch_pending_meta_conversions")
    _configure_meta(monkeypatch)
    consented_at = datetime.now(timezone.utc)
    verified_user.marketing_measurement_consented_at = consented_at
    await db_session.execute(
        update(User).where(User.id == verified_user.id).values(marketing_measurement_consented_at=consented_at)
    )
    event_id = f"complete-registration:{verified_user.id}"
    assert await meta_capi.enqueue_meta_conversion(
        db_session,
        user=verified_user,
        event_name="CompleteRegistration",
        event_id=event_id,
    )
    await db_session.commit()
    client = _RecordingClient()

    monkeypatch.setattr(settings, "META_CAPI_ENABLED", False)
    disabled = await meta_capi.dispatch_pending_meta_conversions(db_session, client=client)
    assert disabled == {"sent": 0, "retried": 0, "failed": 0, "cancelled": 0, "unsupported": 0}
    assert client.calls == []

    monkeypatch.setattr(settings, "META_CAPI_ENABLED", True)
    unsupported = await meta_capi.dispatch_pending_meta_conversions(db_session, client=client)
    assert unsupported == {"sent": 0, "retried": 0, "failed": 0, "cancelled": 0, "unsupported": 1}
    assert client.calls == []

    row = await db_session.scalar(select(MetaConversionOutbox))
    assert row is not None and row.status == "pending" and row.attempts == 0 and row.sent_at is None


@pytest.mark.asyncio
async def test_dispatch_revalidates_consent_and_cancels_without_network(
    db_session: AsyncSession, verified_user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_meta(monkeypatch)
    verified_user.marketing_measurement_consented_at = datetime.now(timezone.utc)
    event_id = f"complete-registration:{verified_user.id}"
    assert await meta_capi.enqueue_meta_conversion(
        db_session,
        user=verified_user,
        event_name="CompleteRegistration",
        event_id=event_id,
    )
    await db_session.execute(
        update(User).where(User.id == verified_user.id).values(marketing_measurement_consented_at=None)
    )
    await db_session.commit()
    client = _RecordingClient()

    result = await meta_capi.dispatch_pending_meta_conversions(db_session, client=client)

    assert result == {"sent": 0, "retried": 0, "failed": 0, "cancelled": 1, "unsupported": 1}
    assert client.calls == []
    row = await db_session.scalar(select(MetaConversionOutbox))
    assert row is not None and row.status == "cancelled" and row.last_error == "consent_revoked"


@pytest.mark.asyncio
async def test_account_deletion_cancels_pending_meta_outbox(
    client: AsyncClient,
    db_session: AsyncSession,
    verified_user: User,
    auth_headers: Callable[[User], dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_meta(monkeypatch)
    consented_at = datetime.now(timezone.utc)
    verified_user.marketing_measurement_consented_at = consented_at
    await db_session.execute(
        update(User).where(User.id == verified_user.id).values(marketing_measurement_consented_at=consented_at)
    )
    assert await meta_capi.enqueue_meta_conversion(
        db_session,
        user=verified_user,
        event_name="CompleteRegistration",
        event_id=f"complete-registration:{verified_user.id}",
    )
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/delete-account",
        json={"password": "supersecret"},
        headers=auth_headers(verified_user),
    )

    assert response.status_code == 200
    db_session.expire_all()
    row = await db_session.scalar(select(MetaConversionOutbox))
    user = await db_session.get(User, verified_user.id)
    assert row is not None and row.status == "cancelled" and row.last_error == "account_deleted"
    assert user is not None and user.marketing_measurement_consented_at is None and user.plan == "deleted"


@pytest.mark.asyncio
async def test_successful_email_verification_enqueues_one_deterministic_complete_registration(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_meta(monkeypatch)
    registered = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "meta-consented@example.com",
            "name": "Meta Consented",
            "password": "Secret123",
            "consent": True,
            "marketing_measurement_consent": True,
        },
    )
    assert registered.status_code == 201
    user = await db_session.scalar(select(User).where(User.email == "meta-consented@example.com"))
    assert user is not None and user.verification_code is not None

    verified = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": user.email, "code": user.verification_code},
    )
    repeated = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": user.email, "code": user.verification_code},
    )

    assert verified.status_code == 200
    assert repeated.status_code == 200
    rows = list(await db_session.scalars(select(MetaConversionOutbox)))
    assert len(rows) == 1
    assert rows[0].event_name == "CompleteRegistration"
    assert rows[0].event_id == f"complete-registration:{user.id}"


@pytest.mark.asyncio
async def test_canonical_paid_transition_enqueues_one_deterministic_purchase(
    db_session: AsyncSession,
    verified_user: User,
    purchase_factory: _PurchaseFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.payments.service import _apply_payment_event

    _configure_meta(monkeypatch)
    await db_session.execute(
        update(User)
        .where(User.id == verified_user.id)
        .values(marketing_measurement_consented_at=datetime.now(timezone.utc))
    )
    await db_session.commit()
    purchase = await purchase_factory(provider="stripe", snapshot=True)

    applied = await _apply_payment_event(
        db_session,
        purchase_id=purchase.id,
        provider="stripe",
        event_key="evt_meta_purchase_paid",
        event_type="checkout.session.completed",
        transition="paid",
        external_payment_id="pi_meta_purchase_paid",
        external_checkout_id=purchase.mp_preference_id,
        validate=lambda _purchase: True,
    )
    repeated = await _apply_payment_event(
        db_session,
        purchase_id=purchase.id,
        provider="stripe",
        event_key="evt_meta_purchase_paid",
        event_type="checkout.session.completed",
        transition="paid",
        external_payment_id="pi_meta_purchase_paid",
        external_checkout_id=purchase.mp_preference_id,
        validate=lambda _purchase: True,
    )

    assert applied.applied is True
    assert repeated.applied is False
    rows = list(await db_session.scalars(select(MetaConversionOutbox)))
    assert len(rows) == 1
    assert rows[0].event_name == "Purchase"
    assert rows[0].event_id == f"purchase:{purchase.id}:paid"
    assert rows[0].payload["custom_data"] == {
        "currency": "BRL",
        "value": purchase.price_brl / 100,
    }


@pytest.mark.asyncio
async def test_meta_enqueue_failure_never_rolls_back_email_verification(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_meta(monkeypatch)
    registered = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "meta-enqueue-failure@example.com",
            "name": "Meta Enqueue Failure",
            "password": "Secret123",
            "consent": True,
            "marketing_measurement_consent": True,
        },
    )
    assert registered.status_code == 201
    user = await db_session.scalar(select(User).where(User.email == "meta-enqueue-failure@example.com"))
    assert user is not None and user.verification_code is not None
    user_id = user.id

    async def fail_enqueue(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("optional marketing persistence failed")

    monkeypatch.setattr(meta_capi, "enqueue_meta_conversion", fail_enqueue)
    response = await client.post(
        "/api/v1/auth/verify-email",
        json={"email": user.email, "code": user.verification_code},
    )

    assert response.status_code == 200
    db_session.expire_all()
    persisted = await db_session.get(User, user_id)
    assert persisted is not None and persisted.email_verified is True
    assert await db_session.scalar(select(func.count()).select_from(MetaConversionOutbox)) == 0


@pytest.mark.asyncio
async def test_meta_enqueue_failure_never_rolls_back_paid_transition(
    db_session: AsyncSession,
    verified_user: User,
    purchase_factory: _PurchaseFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.payments.service import _apply_payment_event

    _configure_meta(monkeypatch)
    await db_session.execute(
        update(User)
        .where(User.id == verified_user.id)
        .values(marketing_measurement_consented_at=datetime.now(timezone.utc))
    )
    await db_session.commit()
    purchase = await purchase_factory(provider="stripe", snapshot=True)
    initial_credits = (await db_session.get(User, verified_user.id)).credits

    async def fail_enqueue(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("optional marketing persistence failed")

    monkeypatch.setattr(meta_capi, "enqueue_meta_conversion", fail_enqueue)
    result = await _apply_payment_event(
        db_session,
        purchase_id=purchase.id,
        provider="stripe",
        event_key="evt_meta_failure_paid",
        event_type="checkout.session.completed",
        transition="paid",
        external_payment_id="pi_meta_failure_paid",
        external_checkout_id=purchase.mp_preference_id,
        validate=lambda _purchase: True,
    )

    assert result.applied is True
    db_session.expire_all()
    persisted_purchase = await db_session.get(type(purchase), purchase.id)
    persisted_user = await db_session.get(User, verified_user.id)
    assert persisted_purchase is not None and persisted_purchase.payment_state == "paid"
    assert persisted_user is not None and persisted_user.credits == initial_credits + purchase.credits_amount
    assert await db_session.scalar(select(func.count()).select_from(MetaConversionOutbox)) == 0
