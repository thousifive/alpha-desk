"""Tests for TODO(me) #1: app.game.levels.level_for_xp. Remove `pytestmark` when done."""

import pytest

from app.game.levels import level_for_xp

pytestmark = pytest.mark.xfail(reason="TODO(me) #1: implement level_for_xp", strict=True)

THRESHOLDS = [0, 500, 1500, 3500, 7000, 12000]


@pytest.mark.parametrize(
    ("xp", "expected"),
    [
        (0, 0),
        (1, 0),
        (499, 0),
        (500, 1),  # exactly on a threshold → reached it
        (501, 1),
        (1499, 1),
        (1500, 2),
        (6999, 3),
        (7000, 4),
        (12000, 5),
        (1_000_000, 5),  # max level caps out
    ],
)
def test_level_for_xp(xp: int, expected: int) -> None:
    assert level_for_xp(xp, THRESHOLDS) == expected


def test_negative_xp_rejected() -> None:
    with pytest.raises(ValueError):
        level_for_xp(-1, THRESHOLDS)


def test_works_with_any_thresholds() -> None:
    assert level_for_xp(10, [0, 10, 20]) == 1
    assert level_for_xp(5, [0]) == 0
