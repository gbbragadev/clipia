from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

PublicPackageIntent = Literal["starter", "popular", "professional"]
CheckoutPackageKey = Literal["starter", "popular", "professional", "pro"]

PUBLIC_PACKAGE_INTENTS: tuple[PublicPackageIntent, ...] = ("starter", "popular", "professional")
_PUBLIC_TO_INTERNAL_PACKAGE: dict[PublicPackageIntent, str] = {
    "starter": "starter",
    "popular": "popular",
    "professional": "pro",
}
_INTERNAL_TO_PUBLIC_PACKAGE = {internal: public for public, internal in _PUBLIC_TO_INTERNAL_PACKAGE.items()}


def normalize_checkout_package(value: str) -> str:
    """Return the stable internal package key used in financial snapshots."""
    normalized = str(value).strip().lower()
    if normalized == "professional":
        return "pro"
    return normalized


def public_package_intent(internal_key: str) -> PublicPackageIntent:
    try:
        return _INTERNAL_TO_PUBLIC_PACKAGE[internal_key]
    except KeyError as exc:
        raise ValueError("Invalid credit package") from exc


@dataclass(frozen=True)
class CreditTariffs:
    standard_voice: Decimal = Decimal("1")
    dialogue: Decimal = Decimal("2")
    script_refinement: Decimal = Decimal("0.5")
    ai_image: Decimal = Decimal("5")
    ai_video: Decimal = Decimal("30")


CREDIT_TARIFFS = CreditTariffs()


def credit_equivalences(total_credits: int) -> dict[str, int]:
    available = Decimal(total_credits)
    return {
        "standard_voice": int(available // CREDIT_TARIFFS.standard_voice),
        "dialogue": int(available // CREDIT_TARIFFS.dialogue),
        "script_refinement": int(available // CREDIT_TARIFFS.script_refinement),
        "ai_image": int(available // CREDIT_TARIFFS.ai_image),
        "ai_video": int(available // CREDIT_TARIFFS.ai_video),
    }
