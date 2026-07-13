from __future__ import annotations

import hashlib
import json
from typing import Any

PAYMENT_SNAPSHOT_VERSION = 1
_SNAPSHOT_METADATA_KEYS = frozenset(
    {
        "purchase_id",
        "provider",
        "package",
        "credits",
        "bonus",
        "amount_cents",
        "currency",
        "snapshot_version",
        "snapshot_hash",
    }
)


def snapshot_payload(
    *,
    purchase_id: object,
    provider: str,
    package: str,
    credits: int,
    bonus: int,
    amount_cents: int,
    currency: str,
) -> tuple[dict[str, str | int], str]:
    payload: dict[str, str | int] = {
        "purchase_id": str(purchase_id),
        "provider": str(provider).strip().lower(),
        "package": str(package).strip(),
        "credits": int(credits),
        "bonus": int(bonus),
        "amount_cents": int(amount_cents),
        "currency": str(currency).strip().upper(),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return payload, hashlib.sha256(encoded).hexdigest()


def _purchase_snapshot(purchase: Any) -> tuple[dict[str, str | int], str]:
    return snapshot_payload(
        purchase_id=purchase.id,
        provider=purchase.provider,
        package=purchase.package_name,
        credits=purchase.credits_amount,
        bonus=purchase.bonus_credits,
        amount_cents=purchase.price_brl,
        currency=purchase.currency,
    )


def freeze_purchase_snapshot(purchase: Any) -> None:
    if int(purchase.credits_amount) <= 0:
        raise ValueError("Purchase credits must be positive")
    if int(purchase.bonus_credits) < 0:
        raise ValueError("Purchase bonus cannot be negative")
    if int(purchase.price_brl) <= 0:
        raise ValueError("Purchase amount must be positive")
    purchase.currency = str(purchase.currency).strip().upper()
    _payload, digest = _purchase_snapshot(purchase)
    purchase.snapshot_version = PAYMENT_SNAPSHOT_VERSION
    purchase.snapshot_hash = digest


def build_snapshot_metadata(purchase: Any) -> dict[str, str]:
    payload, digest = _purchase_snapshot(purchase)
    if purchase.snapshot_version != PAYMENT_SNAPSHOT_VERSION or purchase.snapshot_hash != digest:
        raise ValueError("Purchase snapshot is not frozen or has been mutated")
    return {
        "purchase_id": str(payload["purchase_id"]),
        "provider": str(payload["provider"]),
        "package": str(payload["package"]),
        "credits": str(payload["credits"]),
        "bonus": str(payload["bonus"]),
        "amount_cents": str(payload["amount_cents"]),
        "currency": str(payload["currency"]),
        "snapshot_version": str(PAYMENT_SNAPSHOT_VERSION),
        "snapshot_hash": digest,
    }


def validate_snapshot_metadata(purchase: Any, metadata: object) -> bool:
    if purchase.snapshot_version != PAYMENT_SNAPSHOT_VERSION or not isinstance(metadata, dict):
        return False
    try:
        expected = build_snapshot_metadata(purchase)
    except (AttributeError, TypeError, ValueError):
        return False
    normalized = {str(key): str(value) for key, value in metadata.items()}
    return normalized.keys() == _SNAPSHOT_METADATA_KEYS and normalized == expected
