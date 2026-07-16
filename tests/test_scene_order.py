import pytest

from app.services.scene_order import apply_scene_order, validate_scene_order


def test_valid_scene_order_reorders_authoritative_items():
    order = validate_scene_order([2, 0, 1], 3, strict=True)

    assert apply_scene_order(["scene_0.mp4", "scene_1.mp4", "scene_2.mp4"], order) == [
        "scene_2.mp4",
        "scene_0.mp4",
        "scene_1.mp4",
    ]


@pytest.mark.parametrize("value", [[0, 0], [-1, 0], [0], [0, 2], [True, 0]])
def test_invalid_scene_order_is_rejected_in_strict_mode(value):
    with pytest.raises(ValueError, match="scene order"):
        validate_scene_order(value, 2, strict=True)


def test_invalid_legacy_scene_order_falls_back_to_identity():
    assert validate_scene_order([1, 1], 2, strict=False) == [0, 1]


def test_order_is_not_applied_when_asset_count_differs():
    assert apply_scene_order(["background.mp4"], [1, 0]) == ["background.mp4"]
