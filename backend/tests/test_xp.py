"""Tests for TODO(me) #2: app.game.xp.xp_for_attempt. Remove `pytestmark` when done."""

import pytest

from app.content.schema import XpRules
from app.game.xp import xp_for_attempt

pytestmark = pytest.mark.xfail(reason="TODO(me) #2: implement xp_for_attempt", strict=True)

RULES = XpRules(
    base_by_difficulty={1: 20, 2: 40, 3: 70},
    first_try_bonus=0.25,
    hint_penalty=[0.0, 0.1, 0.25, 0.5],
)


@pytest.mark.parametrize(
    ("difficulty", "first_try", "hints", "expected"),
    [
        (1, False, 0, 20),
        (2, False, 0, 40),
        (3, False, 0, 70),
        (1, True, 0, 25),  # 20 * 1.25
        (2, True, 0, 50),
        (3, True, 0, 87),  # 87.5 rounds DOWN
        (2, False, 1, 36),  # 40 * 0.9
        (2, True, 1, 45),  # 50 * 0.9
        (3, True, 2, 65),  # 87.5 * 0.75 = 65.625 → 65
        (2, False, 3, 20),  # 40 * 0.5
        (2, False, 7, 20),  # beyond the list → last penalty
    ],
)
def test_xp_for_attempt(difficulty: int, first_try: bool, hints: int, expected: int) -> None:
    got = xp_for_attempt(difficulty, first_try=first_try, hints_used=hints, rules=RULES)
    assert got == expected
    assert isinstance(got, int)


def test_unknown_difficulty_rejected() -> None:
    with pytest.raises(ValueError):
        xp_for_attempt(4, first_try=False, hints_used=0, rules=RULES)


def test_negative_hints_rejected() -> None:
    with pytest.raises(ValueError):
        xp_for_attempt(1, first_try=False, hints_used=-1, rules=RULES)
