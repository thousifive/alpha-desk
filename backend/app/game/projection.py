"""Fold the event log into the facts every screen is built from.

Pure and order-independent: the same set of events gives the same result no matter which
device logged them or in what order they arrived. Runs in CPython (server) and in Pyodide
(browser) unchanged.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date

from app.events.schema import AnyEvent, AttemptEvent, QuestCompletedEvent, XpAwardedEvent


@dataclass(frozen=True)
class Derived:
    passed: frozenset[str] = frozenset()
    # slug → (passed attempts, total attempts); feeds first-try XP and quest weakness.
    attempts: dict[str, tuple[int, int]] = field(default_factory=dict)
    xp_total: int = 0
    paid_keys: frozenset[str] = frozenset()
    # Player-local days with at least one passed attempt. Streaks are computed from this.
    active_days: frozenset[date] = frozenset()
    quests_done: frozenset[tuple[date, int]] = frozenset()  # (day, position)
    event_count: int = 0


def _order(e: AnyEvent) -> tuple[str, str]:
    # Sort by creation time, then id as a tiebreak, so "first" is the same on every device.
    # ISO strings of aware datetimes in UTC sort the same as the datetimes themselves.
    return (e.created_at.isoformat(), str(e.id))


def project(events: Iterable[AnyEvent]) -> Derived:
    seen: set[str] = set()
    passed: set[str] = set()
    attempts: dict[str, tuple[int, int]] = {}
    paid: set[str] = set()
    xp = 0
    days: set[date] = set()
    quests: set[tuple[date, int]] = set()

    # sorted() materializes the iterable once, so a generator input is fine.
    for e in sorted(events, key=_order):
        eid = str(e.id)
        if eid in seen:  # the same event imported twice: count it once
            continue
        seen.add(eid)
        # `match` on the event class is a type-narrowing switch (like a TS discriminated union).
        match e:
            case AttemptEvent(payload=p):
                ok, n = attempts.get(p.exercise_slug, (0, 0))
                attempts[p.exercise_slug] = (ok + p.passed, n + 1)
                if p.passed:
                    passed.add(p.exercise_slug)
                    days.add(e.local_date)
            case XpAwardedEvent(payload=p):
                # First event per ref_key wins: the same thing paid on two offline devices
                # merges into one payout.
                if p.ref_key not in paid:
                    paid.add(p.ref_key)
                    xp += p.amount
            case QuestCompletedEvent(payload=p):
                quests.add((p.day, p.position))
            case _:
                pass  # flashcards, hints, achievements: stored now, projected from M3/M4

    return Derived(
        passed=frozenset(passed),
        attempts=attempts,
        xp_total=xp,
        paid_keys=frozenset(paid),
        active_days=frozenset(days),
        quests_done=frozenset(quests),
        event_count=len(seen),
    )
