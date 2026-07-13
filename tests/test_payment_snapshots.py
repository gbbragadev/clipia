import hashlib
import json
from types import SimpleNamespace

import pytest
import stripe
from mercadopago.config import RequestOptions
from sqlalchemy import func, select

from app.db.models import CreditPurchase, PaymentCheckoutDispatch, User
from app.payments.checkout_outbox import CheckoutPending
from app.payments.service import create_checkout, create_checkout_stripe, process_webhook
from app.payments.snapshot import (
    PAYMENT_SNAPSHOT_VERSION,
    build_snapshot_metadata,
    freeze_purchase_snapshot,
    snapshot_payload,
    validate_snapshot_metadata,
)

MP_PREFERENCE_ID = "202809963-a2201f8d-11cb-443f-adf6-de5a42eed67d"
MP_CHECKOUT_URL = f"https://www.mercadopago.com/mla/checkout/start?pref_id={MP_PREFERENCE_ID}"
STRIPE_SESSION_ID = "cs_test_a11YYufWQzNY63zpQ6QSNRQhkUpVph4WRmzW0zWJO2znZKdVujZ0N0S22u"
STRIPE_CHECKOUT_URL = f"https://checkout.stripe.com/c/pay/{STRIPE_SESSION_ID}"


def test_snapshot_hash_is_deterministic_over_exact_frozen_financial_fields():
    fields = {
        "purchase_id": "00000000-0000-0000-0000-000000000001",
        "provider": "stripe",
        "package": "starter",
        "credits": 10,
        "bonus": 2,
        "amount_cents": 1990,
        "currency": "BRL",
    }
    canonical = json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    expected_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    payload, digest = snapshot_payload(**fields)

    assert payload == fields
    assert digest == expected_hash


def test_snapshot_metadata_round_trips_and_rejects_any_tampered_field():
    purchase = CreditPurchase(
        id="00000000-0000-0000-0000-000000000001",
        user_id="00000000-0000-0000-0000-000000000002",
        package_name="starter",
        credits_amount=10,
        bonus_credits=2,
        price_brl=1990,
        provider="stripe",
        currency="BRL",
        status="pending",
    )
    freeze_purchase_snapshot(purchase)
    metadata = build_snapshot_metadata(purchase)

    assert purchase.snapshot_version == PAYMENT_SNAPSHOT_VERSION == 1
    assert len(purchase.snapshot_hash) == 64
    assert validate_snapshot_metadata(purchase, metadata) is True
    assert metadata == {
        "purchase_id": str(purchase.id),
        "provider": "stripe",
        "package": "starter",
        "credits": "10",
        "bonus": "2",
        "amount_cents": "1990",
        "currency": "BRL",
        "snapshot_version": "1",
        "snapshot_hash": purchase.snapshot_hash,
    }

    for key in metadata:
        tampered = dict(metadata)
        tampered[key] = f"{tampered[key]}-tampered"
        assert validate_snapshot_metadata(purchase, tampered) is False, key


@pytest.mark.asyncio
async def test_mp_checkout_persists_pending_before_provider_and_sends_snapshot_and_idempotency(
    test_db, db_session, verified_user, monkeypatch
):
    observed: dict = {}

    class _Preference:
        @staticmethod
        def create(payload, request_options=None):
            observed["payload"] = payload
            observed["request_options"] = request_options
            return {
                "status": 201,
                "response": {"id": MP_PREFERENCE_ID, "init_point": MP_CHECKOUT_URL},
            }

    class _Sdk:
        @staticmethod
        def preference():
            return _Preference()

    monkeypatch.setattr("app.payments.service._get_sdk", lambda: _Sdk())

    original_create = _Preference.create

    def assert_pending_then_create(payload, request_options=None):
        async def load_pending():
            async with test_db["session_factory"]() as verification_session:
                return await verification_session.scalar(select(CreditPurchase))

        import asyncio

        pending = asyncio.run(load_pending())
        assert pending is not None
        assert pending.mp_preference_id is None
        assert pending.status == "pending"
        assert pending.payment_state == "pending"
        assert pending.snapshot_version == 1
        return original_create(payload, request_options)

    monkeypatch.setattr(_Preference, "create", staticmethod(assert_pending_then_create))

    checkout_url, purchase_id = await create_checkout(verified_user, "starter", db_session)

    purchase = await db_session.get(CreditPurchase, purchase_id)
    metadata = observed["payload"]["metadata"]
    assert checkout_url == MP_CHECKOUT_URL
    assert purchase.mp_preference_id == MP_PREFERENCE_ID
    assert validate_snapshot_metadata(purchase, metadata) is True
    assert isinstance(observed["request_options"], RequestOptions)
    assert observed["request_options"].get_headers()["x-idempotency-key"] == (
        f"clipia:checkout:mercadopago:{purchase_id}"
    )


@pytest.mark.asyncio
async def test_stripe_checkout_sends_same_snapshot_to_session_and_payment_intent(
    db_session, verified_user, monkeypatch
):
    captured: dict = {}

    def create_session(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id=STRIPE_SESSION_ID, url=STRIPE_CHECKOUT_URL)

    monkeypatch.setattr("app.payments.service.settings.STRIPE_SECRET_KEY", "sk_test")
    monkeypatch.setattr(stripe.checkout.Session, "create", staticmethod(create_session))

    checkout_url, purchase_id = await create_checkout_stripe(verified_user, "starter", db_session)

    purchase = await db_session.get(CreditPurchase, purchase_id)
    assert checkout_url == STRIPE_CHECKOUT_URL
    assert captured["metadata"] == captured["payment_intent_data"]["metadata"]
    assert validate_snapshot_metadata(purchase, captured["metadata"]) is True
    assert captured["idempotency_key"] == f"clipia:checkout:stripe:{purchase_id}"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider", "provider_result"),
    [
        ("mercadopago", {"status": 201, "response": {"id": "", "init_point": MP_CHECKOUT_URL}}),
        ("mercadopago", {"status": 201, "response": {"id": MP_PREFERENCE_ID, "init_point": ""}}),
        ("stripe", SimpleNamespace(id="", url=STRIPE_CHECKOUT_URL)),
        ("stripe", SimpleNamespace(id=STRIPE_SESSION_ID, url="")),
    ],
)
async def test_checkout_quarantines_missing_provider_identity_or_url_without_voiding_purchase(
    test_db, db_session, verified_user, monkeypatch, provider, provider_result
):
    if provider == "mercadopago":

        class _Preference:
            @staticmethod
            def create(_payload, request_options=None):
                return provider_result

        class _Sdk:
            @staticmethod
            def preference():
                return _Preference()

        monkeypatch.setattr("app.payments.service._get_sdk", lambda: _Sdk())
        checkout = create_checkout
    else:
        monkeypatch.setattr("app.payments.service.settings.STRIPE_SECRET_KEY", "sk_test")
        monkeypatch.setattr(stripe.checkout.Session, "create", staticmethod(lambda **_kwargs: provider_result))
        checkout = create_checkout_stripe

    with pytest.raises(CheckoutPending):
        await checkout(verified_user, "starter", db_session)

    async with test_db["session_factory"]() as verification_session:
        purchase = await verification_session.scalar(select(CreditPurchase))
        dispatch = await verification_session.scalar(select(PaymentCheckoutDispatch))
        assert purchase is not None
        assert purchase.status == "pending"
        assert purchase.payment_state == "pending"
        assert purchase.mp_preference_id is None
        assert purchase.mp_payment_id is None
        assert dispatch is not None
        assert dispatch.state == "pending"
        assert dispatch.provider_checkout_id is None
        assert dispatch.checkout_url is None
        assert dispatch.error_code == "provider_unavailable"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider", "provider_result"),
    [
        (
            "mercadopago",
            {"status": 201, "response": {"id": "garbage", "init_point": MP_CHECKOUT_URL}},
        ),
        (
            "mercadopago",
            {"status": 201, "response": {"id": MP_PREFERENCE_ID, "init_point": "javascript:alert(1)"}},
        ),
        (
            "mercadopago",
            {
                "status": 201,
                "response": {
                    "id": MP_PREFERENCE_ID,
                    "init_point": "https://www.mercadopago.com.evil.example/checkout",
                },
            },
        ),
        (
            "mercadopago",
            {
                "status": 201,
                "response": {
                    "id": MP_PREFERENCE_ID,
                    "init_point": "https://user@www.mercadopago.com/checkout",
                },
            },
        ),
        (
            "stripe",
            SimpleNamespace(id="garbage", url=STRIPE_CHECKOUT_URL),
        ),
        (
            "stripe",
            SimpleNamespace(id=STRIPE_SESSION_ID, url="http://checkout.stripe.com/c/pay/test"),
        ),
        (
            "stripe",
            SimpleNamespace(id=STRIPE_SESSION_ID, url="https://stripe.example/c/pay/test"),
        ),
        (
            "stripe",
            SimpleNamespace(id=STRIPE_SESSION_ID, url="https://user@checkout.stripe.com/c/pay/test"),
        ),
        (
            "stripe",
            SimpleNamespace(id=STRIPE_SESSION_ID, url="https://checkout.stripe.com:444/c/pay/test"),
        ),
    ],
)
async def test_checkout_quarantines_malformed_identity_or_untrusted_redirect_without_voiding_purchase(
    test_db, db_session, verified_user, monkeypatch, provider, provider_result
):
    if provider == "mercadopago":

        class _Preference:
            @staticmethod
            def create(_payload, request_options=None):
                return provider_result

        class _Sdk:
            @staticmethod
            def preference():
                return _Preference()

        monkeypatch.setattr("app.payments.service._get_sdk", lambda: _Sdk())
        checkout = create_checkout
    else:
        monkeypatch.setattr("app.payments.service.settings.STRIPE_SECRET_KEY", "sk_test")
        monkeypatch.setattr(stripe.checkout.Session, "create", staticmethod(lambda **_kwargs: provider_result))
        checkout = create_checkout_stripe

    with pytest.raises(CheckoutPending):
        await checkout(verified_user, "starter", db_session)

    async with test_db["session_factory"]() as verification_session:
        purchase = await verification_session.scalar(select(CreditPurchase))
        dispatch = await verification_session.scalar(select(PaymentCheckoutDispatch))
        assert purchase is not None
        assert purchase.status == "pending"
        assert purchase.payment_state == "pending"
        assert purchase.mp_preference_id is None
        assert purchase.mp_payment_id is None
        assert dispatch is not None
        assert dispatch.state == "pending"
        assert dispatch.provider_checkout_id is None
        assert dispatch.checkout_url is None
        assert dispatch.error_code == "provider_unavailable"


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["mercadopago", "stripe"])
async def test_ambiguous_provider_exception_keeps_purchase_and_dispatch_pending(
    test_db, db_session, verified_user, monkeypatch, provider
):
    if provider == "mercadopago":

        class _Preference:
            @staticmethod
            def create(_payload, request_options=None):
                raise RuntimeError("provider unavailable")

        class _Sdk:
            @staticmethod
            def preference():
                return _Preference()

        monkeypatch.setattr("app.payments.service._get_sdk", lambda: _Sdk())
        checkout = create_checkout
    else:
        monkeypatch.setattr("app.payments.service.settings.STRIPE_SECRET_KEY", "sk_test")
        monkeypatch.setattr(
            stripe.checkout.Session,
            "create",
            staticmethod(lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("provider unavailable"))),
        )
        checkout = create_checkout_stripe

    with pytest.raises(CheckoutPending):
        await checkout(verified_user, "starter", db_session)

    async with test_db["session_factory"]() as verification_session:
        purchase = await verification_session.scalar(select(CreditPurchase))
        dispatch = await verification_session.scalar(select(PaymentCheckoutDispatch))
        assert purchase is not None
        assert purchase.payment_state == "pending"
        assert purchase.mp_preference_id is None
        assert dispatch is not None
        assert dispatch.state == "pending"
        assert dispatch.error_code == "provider_unavailable"


@pytest.mark.asyncio
async def test_initial_pending_commit_failure_never_calls_provider(db_session, verified_user, monkeypatch):
    provider_calls = 0

    class _Preference:
        @staticmethod
        def create(_payload, request_options=None):
            nonlocal provider_calls
            provider_calls += 1
            raise AssertionError("provider must not run before pending commit")

    class _Sdk:
        @staticmethod
        def preference():
            return _Preference()

    monkeypatch.setattr("app.payments.service._get_sdk", lambda: _Sdk())

    async def fail_commit():
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(db_session, "commit", fail_commit)

    with pytest.raises(RuntimeError, match="database unavailable"):
        await create_checkout(verified_user, "starter", db_session)

    assert provider_calls == 0
    await db_session.rollback()
    assert await db_session.scalar(select(func.count()).select_from(CreditPurchase)) == 0


@pytest.mark.asyncio
async def test_checkout_binding_commit_failure_keeps_durable_pending_purchase_recoverable_by_webhook(
    test_db, db_session, verified_user, monkeypatch
):
    observed: dict = {}

    class _Preference:
        @staticmethod
        def create(payload, request_options=None):
            observed["metadata"] = payload["metadata"]
            return {
                "status": 201,
                "response": {"id": MP_PREFERENCE_ID, "init_point": MP_CHECKOUT_URL},
            }

    class _Sdk:
        @staticmethod
        def preference():
            return _Preference()

        @staticmethod
        def payment():
            class _Payment:
                @staticmethod
                def get(payment_id):
                    return {
                        "status": 200,
                        "response": {
                            "id": str(payment_id),
                            "status": "approved",
                            "external_reference": observed["metadata"]["purchase_id"],
                            "transaction_amount": 19.90,
                            "currency_id": "BRL",
                            "preference_id": MP_PREFERENCE_ID,
                            "metadata": observed["metadata"],
                        },
                    }

            return _Payment()

    monkeypatch.setattr("app.payments.service._get_sdk", lambda: _Sdk())
    original_commit = db_session.commit
    commit_calls = 0

    async def fail_only_checkout_binding_commit():
        nonlocal commit_calls
        commit_calls += 1
        if commit_calls == 3:
            raise RuntimeError("binding commit failed")
        await original_commit()

    monkeypatch.setattr(db_session, "commit", fail_only_checkout_binding_commit)

    with pytest.raises(CheckoutPending):
        await create_checkout(verified_user, "starter", db_session)

    async with test_db["session_factory"]() as verification_session:
        purchase = await verification_session.scalar(select(CreditPurchase))
        dispatch = await verification_session.scalar(select(PaymentCheckoutDispatch))
        assert purchase is not None
        assert purchase.payment_state == "pending"
        assert purchase.mp_preference_id is None
        assert purchase.snapshot_version == 1
        assert dispatch is not None
        assert dispatch.state == "pending"
        assert dispatch.error_code == "binding_failed"

    assert (await process_webhook("123", db_session)).applied is True
    db_session.expire_all()
    recovered = await db_session.scalar(select(CreditPurchase))
    assert recovered.payment_state == "paid"
    assert recovered.mp_preference_id == MP_PREFERENCE_ID
    assert recovered.mp_payment_id == "123"
    assert (await db_session.get(User, verified_user.id)).credits == 15
