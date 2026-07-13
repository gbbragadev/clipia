from __future__ import annotations

from sqlalchemy import ColumnElement, case

CANONICAL_PAYMENT_STATES = frozenset({"pending", "paid", "refunded", "void"})

_LEGACY_TO_CANONICAL = {
    "pending": "pending",
    "approved": "paid",
    "paid": "paid",
    "refunded": "refunded",
    "charged_back": "refunded",
    "cancelled": "void",
    "canceled": "void",
    "rejected": "void",
    "expired": "void",
    "void": "void",
}
_PRECEDENCE = {"pending": 0, "void": 1, "paid": 2, "refunded": 3}
_CANONICAL_TO_LEGACY = {
    "pending": "pending",
    "paid": "approved",
    "refunded": "refunded",
    # Old binaries and the pre-migration database constraint only understand
    # pending/approved/refunded. Keep void retryable for a later paid event.
    "void": "pending",
}


def _normalize(value: str | None) -> str | None:
    if value is None:
        return None
    return str(value).strip().lower()


def canonical_payment_state(status: str | None, payment_state: str | None) -> str:
    """Resolve rolling-deploy columns using terminal-state precedence.

    Old application versions write ``status`` while new versions dual-write both
    columns. Taking the strongest state prevents an old writer from resurrecting
    a refunded purchase during the rollout.
    """
    legacy = _normalize(status)
    canonical = _normalize(payment_state)
    candidates: list[str] = []
    if legacy is not None:
        mapped = _LEGACY_TO_CANONICAL.get(legacy)
        if mapped is None:
            raise ValueError(f"Unsupported payment state: {status}")
        candidates.append(mapped)
    if canonical is not None:
        if canonical not in CANONICAL_PAYMENT_STATES:
            raise ValueError(f"Unsupported payment state: {payment_state}")
        candidates.append(canonical)
    if not candidates:
        raise ValueError("Unsupported payment state: empty")
    return max(candidates, key=_PRECEDENCE.__getitem__)


def canonical_payment_state_or_invalid(status: str | None, payment_state: str | None) -> str:
    """Resolve read-only diagnostics without hiding corrupt persisted values.

    Financial mutations keep using :func:`canonical_payment_state` and fail
    closed. Diagnostics may expose ``__invalid__`` instead of silently treating
    an unsupported rolling-deploy row as pending.
    """
    try:
        return canonical_payment_state(status, payment_state)
    except ValueError:
        return "__invalid__"


def payment_state_values(state: str) -> dict[str, str]:
    canonical = _normalize(state)
    if canonical not in CANONICAL_PAYMENT_STATES:
        raise ValueError(f"Unsupported payment state: {state}")
    return {"payment_state": canonical, "status": _CANONICAL_TO_LEGACY[canonical]}


def canonical_payment_state_expression(status_column, payment_state_column) -> ColumnElement[str]:
    """SQL equivalent of :func:`canonical_payment_state` for trusted rows."""
    legacy = case(
        (status_column.in_(("refunded", "charged_back")), "refunded"),
        (status_column.in_(("approved", "paid")), "paid"),
        (status_column.in_(("cancelled", "canceled", "rejected", "expired", "void")), "void"),
        (status_column == "pending", "pending"),
        else_="__invalid__",
    )
    return case(
        ((payment_state_column == "refunded") | (legacy == "refunded"), "refunded"),
        ((payment_state_column == "paid") | (legacy == "paid"), "paid"),
        ((payment_state_column == "void") | (legacy == "void"), "void"),
        (payment_state_column == "pending", "pending"),
        ((payment_state_column.is_(None)) & (legacy == "pending"), "pending"),
        else_="__invalid__",
    )
