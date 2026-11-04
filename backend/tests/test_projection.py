"""Event log → derived facts, from the shared fixtures in tests/fixtures/events/.

The same fixtures run in the browser's Pyodide worker (frontend kernel.e2e.test.ts), so a rule
change that breaks one side breaks both.
"""

import json
import random
from datetime import date
from pathlib import Path
from typing import Any

import pytest

import app.views as views
from app.config import get_settings
from app.content.loader import load_content
from app.events.schema import EVENT_LIST
from app.game.projection import project
from app.game.streaks import StreakState

FIXTURES = Path(__file__).parent / "fixtures" / "events"
BUNDLE = load_content(get_settings().content_dir)


def _load(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text())


ALL = sorted(p.name for p in FIXTURES.glob("*.json"))


@pytest.mark.parametrize("name", ALL)
def test_fixture_facts(name: str) -> None:
    fx = _load(name)
    d = project(EVENT_LIST.validate_python(fx["events"]))
    want = fx["expect"]["facts"]
    assert d.xp_total == want["xp_total"]
    assert sorted(d.passed) == want["passed"]
    assert {k: list(v) for k, v in d.attempts.items()} == want["attempts"]
    assert sorted(x.isoformat() for x in d.active_days) == want["active_days"]
    assert d.event_count == want["event_count"]


@pytest.mark.parametrize("name", ALL)
def test_arrival_order_does_not_matter(name: str) -> None:
    events = EVENT_LIST.validate_python(_load(name)["events"])
    base = project(events)
    for seed in range(5):
        shuffled = list(events)
        random.Random(seed).shuffle(shuffled)
        assert project(shuffled) == base


def test_first_xp_event_per_key_wins() -> None:
    """The phone's duplicate payout for the quiz is *later* than the iPad's: the iPad's counts."""
    d = project(EVENT_LIST.validate_python(_load("xp_and_passes.json")["events"]))
    assert d.xp_total == 20 + 25
    assert d.paid_keys == {"attempt:sql-first-look", "attempt:quiz-py-generics"}


def test_streak_uses_local_date_not_utc_or_sync_time(monkeypatch: pytest.MonkeyPatch) -> None:
    """The streak engine must see local_date days. The 00:30 IST attempt is Nov 2 in UTC but
    counts for Nov 3, and the late-synced phone days still count."""
    seen: list[set[date]] = []

    def fake(days: Any, today: date, rules: Any) -> StreakState:
        seen.append(set(days))
        return StreakState(4, 4, 0, True, date(2026, 11, 1))

    monkeypatch.setattr(views, "compute_streak", fake)
    fx = _load("offline_streak_late_sync.json")
    d = project(EVENT_LIST.validate_python(fx["events"]))
    views.progress_view(
        BUNDLE,
        passed=set(d.passed),
        xp_total=d.xp_total,
        active_days=d.active_days,
        today=date.fromisoformat(fx["today"]),
        milestone="M2",
    )
    assert seen == [{date(2026, 11, n) for n in (1, 2, 3, 4)}]


# ---- needs TODO(me) #1 level_for_xp and M2-1 compute_streak ----------------------------


@pytest.mark.xfail(reason="needs TODO(me) #1 level_for_xp and M2-1 compute_streak", strict=True)
@pytest.mark.parametrize("name", ALL)
def test_fixture_with_todos(name: str) -> None:
    fx = _load(name)
    d = project(EVENT_LIST.validate_python(fx["events"]))
    p = views.progress_view(
        BUNDLE,
        passed=set(d.passed),
        xp_total=d.xp_total,
        active_days=d.active_days,
        today=date.fromisoformat(fx["today"]),
        milestone="M2",
    )
    want = fx["expect"]["with_todos"]
    if "level" in want:
        assert p.level is not None and p.level.title == want["level"]
    if "streak" in want:
        assert p.streak is not None
        for k, v in want["streak"].items():
            assert getattr(p.streak, k) == v
