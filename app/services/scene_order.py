"""Validation and application helpers for editor scene ordering."""

from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")


def identity_scene_order(scene_count: int) -> list[int]:
    """Return the canonical physical order for a scene count."""
    return list(range(max(0, scene_count)))


def validate_scene_order(value: object, scene_count: int, *, strict: bool) -> list[int]:
    """Validate an exact permutation, or return identity for legacy state."""
    identity = identity_scene_order(scene_count)
    valid = (
        isinstance(value, list)
        and len(value) == scene_count
        and all(type(index) is int for index in value)
        and sorted(value) == identity
    )
    if valid:
        return list(value)
    if value is not None and strict:
        raise ValueError("invalid scene order")
    return identity


def apply_scene_order(items: Sequence[T], order: Sequence[int]) -> list[T]:
    """Apply a validated order only when it covers every authoritative item."""
    if len(items) != len(order):
        return list(items)
    return [items[index] for index in order]
