"""Daily streaks with freeze tokens. Rules come from content/quests.yaml (`streaks:`).

Nothing is stored: the streak is recomputed from the set of days with a passed attempt,
the same way node states are recomputed from attempts (no counter that can drift).
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from app.content.schema import StreakRules


@dataclass(frozen=True)
class StreakState:
    current: int  # length of the live streak, in active days (frozen days don't add)
    best: int  # longest streak ever reached
    freezes: int  # freeze tokens banked right now
    active_today: bool  # has today already counted?
    run_start: date | None  # first active day of the live streak; None when current == 0


def compute_streak(active_days: Iterable[date], today: date, rules: StreakRules) -> StreakState:
    """Walk every calendar day from the first active day up to `today`.

    - Active day: current += 1. Whenever current reaches a multiple of rules.freeze_every,
      bank one freeze (never more than rules.max_freezes).
    - Missed day *before* today: if a freeze is banked, spend it (current is unchanged, the
      run continues). Otherwise the streak breaks: current = 0, run_start = None.
    - Today, not active yet: not a miss. The day isn't over, so the streak stays alive.
    - best = the highest `current` seen at any point.
    - Days after `today` are ignored; duplicates in `active_days` count once.
    - No active days at all → StreakState(0, 0, 0, False, None).

    Example (freeze_every=7): active Nov 1-7, missed Nov 8, active Nov 9, today = Nov 9
    → current=8, freezes=0 (earned on day 7, spent on Nov 8), run_start=Nov 1.

    TODO(me): implement.
    Teaches: `datetime.date` arithmetic with `timedelta`, sets for O(1) membership, frozen
    dataclasses as return values, and edge-case-driven tests (gaps, freezes, "today").
    """
    raise NotImplementedError("TODO(me) M2-1: compute_streak")


def streak_milestone(state: StreakState, rules: StreakRules) -> int | None:
    """The milestone just reached today (7, 14, …), if any. Paid once per run via the ledger."""
    if state.active_today and state.current and state.current % rules.milestone_every == 0:
        return state.current
    return None
