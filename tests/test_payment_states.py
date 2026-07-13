import importlib

import pytest
from sqlalchemy import CheckConstraint, Index

from app.db.models import CreditPurchase


def test_payment_state_adapter_maps_legacy_rows_and_dual_write_values():
    states = importlib.import_module("app.payments.states")

    assert states.canonical_payment_state("approved", None) == "paid"
    assert states.canonical_payment_state("paid", None) == "paid"
    assert states.canonical_payment_state("cancelled", None) == "void"
    assert states.canonical_payment_state("approved", "refunded") == "refunded"
    assert states.payment_state_values("paid") == {"payment_state": "paid", "status": "approved"}
    assert states.payment_state_values("pending") == {"payment_state": "pending", "status": "pending"}
    assert states.payment_state_values("refunded") == {"payment_state": "refunded", "status": "refunded"}
    # During the rolling deploy, old binaries only understand pending/approved/refunded.
    # A canonical void must therefore remain retryable to an old paid-event writer.
    assert states.payment_state_values("void") == {"payment_state": "void", "status": "pending"}
    assert states.canonical_payment_state("pending", "void") == "void"
    assert states.canonical_payment_state("approved", "void") == "paid"


def test_payment_state_adapter_fails_closed_for_unknown_states():
    states = importlib.import_module("app.payments.states")

    with pytest.raises(ValueError, match="Unsupported payment state"):
        states.canonical_payment_state("mystery", None)
    with pytest.raises(ValueError, match="Unsupported payment state"):
        states.payment_state_values("mystery")


def test_credit_purchase_model_declares_canonical_state_and_provider_identity_guards():
    table = CreditPurchase.__table__

    assert table.c.payment_state.nullable is True
    assert any(
        isinstance(constraint, CheckConstraint)
        and "payment_state" in str(constraint.sqltext)
        and all(state in str(constraint.sqltext) for state in ("pending", "paid", "refunded", "void"))
        for constraint in table.constraints
    )
    constraint_names = {constraint.name for constraint in table.constraints if isinstance(constraint, CheckConstraint)}
    assert {
        "ck_credit_purchase_legacy_status",
        "ck_credit_purchase_credits_positive",
        "ck_credit_purchase_bonus_nonnegative",
        "ck_credit_purchase_price_positive",
    } <= constraint_names
    assert any(
        isinstance(constraint, CheckConstraint)
        and constraint.name == "ck_credit_purchase_snapshot_pair"
        and "LENGTH(snapshot_hash) = 64" in str(constraint.sqltext)
        for constraint in table.constraints
    )
    indexes = [index for index in table.indexes if isinstance(index, Index)]
    assert any(index.unique and index.columns.keys() == ["provider", "mp_preference_id"] for index in indexes)
    assert any(index.unique and index.columns.keys() == ["provider", "mp_payment_id"] for index in indexes)


@pytest.mark.asyncio
async def test_purchase_history_exposes_canonical_paid_for_historical_approved(
    client, verified_user, auth_headers, purchase_factory
):
    await purchase_factory(user_id=verified_user.id, status="approved")

    response = await client.get("/api/v1/credits/history", headers=auth_headers(verified_user))

    assert response.status_code == 200
    assert response.json()["purchases"][0]["status"] == "paid"


@pytest.mark.asyncio
async def test_account_export_exposes_canonical_paid_for_historical_approved(
    client, verified_user, auth_headers, purchase_factory
):
    await purchase_factory(user_id=verified_user.id, status="approved")

    response = await client.get("/api/v1/auth/export-data", headers=auth_headers(verified_user))

    assert response.status_code == 200
    assert response.json()["purchases"][0]["status"] == "paid"
