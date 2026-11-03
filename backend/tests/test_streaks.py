"""Tests for TODO(me) M2-1: app.game.streaks.compute_streak.

Remove the `todo` marker from each test (or the whole decorator line) once it's implemented;
xfail is strict, so a passing test that's still marked fails the run.
"""

from datetime import date, timedelta

import pytest

from app.content.schema import StreakRules
from app.game.streaks import StreakState, compute_streak, streak_milestone

todo = pytest.mark.xfail(reason="TODO(me) M2-1: implement compute_streak", strict=True)

RULES = StreakRules(freeze_every=7, max_freezes=2, milestone_every=7, milestone_xp=50)
NOV = date(2026, 11, 1)


def d(n: int) -> date:
    """Day n of the test calendar: d(1) = Nov 1."""
    return NOV + timedelta(days=n - 1)


def days(*ns: int) -> list[date]:
    return [d(n) for n in ns]


@todo
def test_no_activity() -> None:
    assert compute_streak([], d(5), RULES) == StreakState(0, 0, 0, False, None)


@todo
def test_active_today_only() -> None:
    assert compute_streak(days(5), d(5), RULES) == StreakState(1, 1, 0, True, d(5))


@todo
def test_today_not_yet_active_keeps_streak() -> None:
    s = compute_streak(days(1, 2, 3), d(4), RULES)
    assert (s.current, s.active_today, s.run_start) == (3, False, d(1))


@todo
def test_missed_yesterday_without_freeze_breaks() -> None:
    s = compute_streak(days(1, 2, 3), d(5), RULES)
    assert (s.current, s.best, s.run_start) == (0, 3, None)


@todo
def test_seventh_day_earns_a_freeze() -> None:
    s = compute_streak(days(*range(1, 8)), d(7), RULES)
    assert (s.current, s.freezes) == (7, 1)


@todo
def test_freeze_covers_one_missed_day() -> None:
    # Docstring example: active 1-7, miss 8, active 9.
    s = compute_streak(days(*range(1, 8), 9), d(9), RULES)
    assert s == StreakState(current=8, best=8, freezes=0, active_today=True, run_start=d(1))


@todo
def test_freeze_runs_out_on_second_missed_day() -> None:
    s = compute_streak(days(*range(1, 8)), d(10), RULES)  # miss 8 (freeze) and 9 (break)
    assert (s.current, s.best, s.freezes) == (0, 7, 0)


@todo
def test_two_freezes_cover_two_days() -> None:
    s = compute_streak(days(*range(1, 15), 17), d(17), RULES)  # 14 days → 2 freezes; miss 15, 16
    assert (s.current, s.freezes, s.run_start) == (15, 0, d(1))


@todo
def test_freezes_are_capped() -> None:
    s = compute_streak(days(*range(1, 29)), d(28), RULES)  # 28 days would earn 4
    assert s.freezes == 2


@todo
def test_restart_after_break_tracks_best_and_new_run_start() -> None:
    s = compute_streak(days(1, 2, 3, 4, 10, 11), d(11), RULES)
    assert (s.current, s.best, s.run_start) == (2, 4, d(10))


@todo
def test_future_days_and_duplicates_ignored() -> None:
    s = compute_streak([d(1), d(1), d(2), d(9)], d(2), RULES)
    assert (s.current, s.best, s.active_today) == (2, 2, True)


@todo
def test_unsorted_input() -> None:
    s = compute_streak([d(3), d(1), d(2)], d(3), RULES)
    assert s.current == 3


# ---- streak_milestone: not a TODO, always on ------------------------------------------


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (StreakState(7, 7, 1, True, d(1)), 7),
        (StreakState(14, 14, 2, True, d(1)), 14),
        (StreakState(7, 7, 1, False, d(1)), None),  # yesterday's 7, today not active yet
        (StreakState(8, 8, 1, True, d(1)), None),
        (StreakState(0, 3, 0, False, None), None),
    ],
)
def test_streak_milestone(state: StreakState, expected: int | None) -> None:
    assert streak_milestone(state, RULES) == expected
