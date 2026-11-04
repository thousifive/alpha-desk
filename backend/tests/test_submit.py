"""Offline submit (app.game.submit + app.kernel): grade, then decide the events to append.

Mirrors tests/test_api_m2.py: fakes stand in for the open TODO(me)s so the wiring around them
is tested now; the locked-state tests use the real (unimplemented) functions.
"""

import json
import random
from collections.abc import Iterator, Sequence
from datetime import UTC, date, datetime
from typing import Any

import pytest

import app.game.submit as submit_mod
import app.kernel as kernel
import app.views as views
from app.config import get_settings
from app.content.loader import load_content
from app.events.schema import EVENT_LIST, AnyEvent, XpAwardedEvent
from app.game.projection import project
from app.game.streaks import StreakState
from app.game.submit import Context, SubmitRejected, Verdict, decide, grade
from app.grading.python import PythonGrade
from app.grading.sql import Comparison, ResultSet
from app.schemas import AttemptIn

BUNDLE = load_content(get_settings().content_dir)
TODAY = date(2026, 11, 4)
NOW = datetime(2026, 11, 4, 5, 0, tzinfo=UTC)
QUIZ = "quiz-py-generics"  # root node py-typing, playable from M2
QUIZ_ANSWER = next(
    e for ns in BUNDLE.nodes.values() for n in ns for e in n.exercises if e.slug == QUIZ
).answer  # type: ignore[union-attr]
ROOT = ["sql-first-look", "sql-tech-roster", "sql-heavy-volume-days"]  # node select-filter


def ctx(device: str = "phone") -> Context:
    return Context(device_id=device, now=NOW, today=TODAY, milestone="M2")


def _top_k[T](items: Sequence[T], weights: Sequence[float], k: int, rng: random.Random) -> list[T]:
    return list(items[: max(k, 0)])


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(submit_mod, "xp_for_attempt", lambda *_a, **_k: 10)
    monkeypatch.setattr(
        submit_mod, "compare_result_sets", lambda *_a, **_k: Comparison(passed=True)
    )
    monkeypatch.setattr(submit_mod, "grade_python_report", lambda *_: PythonGrade(True, ""))


def _pass(slug: str, events: list[AnyEvent], device: str = "phone", **kw: Any) -> Any:
    return decide(
        BUNDLE, project(events), slug, AttemptIn(), Verdict(True, "ok"), ctx(device), **kw
    )


# ---- grading -------------------------------------------------------------------------


def test_quiz_grading_is_real() -> None:
    assert grade(BUNDLE, QUIZ, AttemptIn(choice=QUIZ_ANSWER), None).passed
    v = grade(BUNDLE, QUIZ, AttemptIn(choice=(QUIZ_ANSWER + 1) % 2), None)
    assert not v.passed and v.explanation


def test_grade_rejects_missing_answers() -> None:
    with pytest.raises(SubmitRejected):
        grade(BUNDLE, QUIZ, AttemptIn(), None)
    with pytest.raises(SubmitRejected):
        grade(BUNDLE, "sql-first-look", AttemptIn(), None)
    with pytest.raises(SubmitRejected):
        grade(BUNDLE, "no-such-exercise", AttemptIn(), None)


def test_sql_grading_is_locked_until_todo_3() -> None:
    rs = {"columns": ["a"], "rows": [[1]]}
    with pytest.raises(NotImplementedError, match=r"TODO\(me\) #3"):
        grade(BUNDLE, "sql-first-look", AttemptIn(result=rs), ResultSet(["a"], [[1]]))


def test_xp_is_locked_until_todo_2() -> None:
    with pytest.raises(NotImplementedError, match=r"TODO\(me\) #2"):
        _pass(QUIZ, [])


# ---- decide (with fakes) -------------------------------------------------------------


def test_first_pass_pays_once(fakes: None) -> None:
    d1 = _pass(QUIZ, [])
    assert [e.type for e in d1.events] == ["attempt", "xp_awarded"]
    assert d1.out.xp_awarded == 10 and d1.out.xp_total == 10
    d2 = _pass(QUIZ, d1.events)
    assert d2.out.already_passed and d2.out.xp_awarded == 0
    assert [e.type for e in d2.events] == ["attempt"]


def test_failed_attempt_logs_without_xp(fakes: None) -> None:
    d = decide(BUNDLE, project([]), QUIZ, AttemptIn(), Verdict(False, "no"), ctx())
    assert [e.type for e in d.events] == ["attempt"]
    assert d.out.xp_total == 0


def test_locked_node_rejected(fakes: None) -> None:
    with pytest.raises(SubmitRejected, match="locked"):
        _pass("sql-close-with-sector", [])  # needs select-filter mastered


def test_node_bonus_on_mastery(fakes: None) -> None:
    events: list[AnyEvent] = []
    for slug in ROOT:
        d = _pass(slug, events)
        events += d.events
    assert d.out.node_bonus_xp == 50
    assert project(events).xp_total == 3 * 10 + 50


def test_quest_completion_and_all_done_bonus(fakes: None) -> None:
    plan = [(0, ROOT[0]), (1, QUIZ)]
    rules = BUNDLE.quests.quests
    d1 = _pass(ROOT[0], [], quest_plan=plan)
    assert d1.out.quest_position == 0 and d1.out.quest_xp == rules.xp_per_quest
    assert not d1.out.quests_all_done
    d2 = _pass(QUIZ, d1.events, quest_plan=plan)
    assert d2.out.quests_all_done
    assert d2.out.quest_xp == rules.xp_per_quest + rules.all_done_bonus
    assert project(d1.events + d2.events).quests_done == {(TODAY, 0), (TODAY, 1)}


def test_two_offline_devices_merge_without_double_pay(fakes: None) -> None:
    """Phone and iPad both solve the quiz offline from the same starting state."""
    phone = _pass(QUIZ, [], device="phone")
    ipad = _pass(QUIZ, [], device="ipad")
    merged = project(phone.events + ipad.events)
    assert merged.xp_total == 10  # one payout for attempt:quiz-py-generics
    assert merged.attempts[QUIZ] == (2, 2)  # both attempts are still in the history


def test_streak_milestone_paid_once_per_run(fakes: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(views, "compute_streak", lambda *_: StreakState(7, 7, 1, True, TODAY))
    d1 = _pass(QUIZ, [])
    assert d1.out.streak_xp == BUNDLE.quests.streaks.milestone_xp
    d2 = _pass(ROOT[0], d1.events)
    assert d2.out.streak_xp == 0


# ---- kernel (the JSON boundary the browser calls) ------------------------------------


@pytest.fixture
def k() -> Iterator[Any]:
    payload = {
        "version": "test",
        "milestone": "M2",
        "content": BUNDLE.model_dump(mode="json"),
    }
    kernel.load_bundle(json.dumps(payload))
    kernel.reset_events()
    yield kernel
    kernel.reset_events()


def _req(**kw: Any) -> str:
    base = {
        "slug": QUIZ,
        "attempt": {"choice": QUIZ_ANSWER},
        "device_id": "phone",
        "now": NOW.isoformat(),
        "today": TODAY.isoformat(),
    }
    return json.dumps(base | kw)


def test_kernel_bundle_round_trips(k: Any) -> None:
    assert k._bundle() == BUNDLE  # JSON → ContentBundle loses nothing


def test_kernel_snapshot_shape(k: Any) -> None:
    snap = json.loads(k.snapshot(TODAY.isoformat()))
    assert snap["progress"]["next_boss"]["title"] == "The Analytics Desk"
    assert {b["id"] for b in snap["branches"]} == set(snap["details"])
    assert snap["event_count"] == 0


def test_kernel_submit_locked(k: Any) -> None:
    res = json.loads(k.submit(_req()))
    assert res["status"] == "locked"
    assert "TODO(me) #2" in res["message"]


def test_kernel_submit_rejected(k: Any) -> None:
    assert json.loads(k.submit(_req(attempt={})))["status"] == "rejected"


def test_kernel_submit_then_snapshot(k: Any, fakes: None) -> None:
    res = json.loads(k.submit(_req()))
    assert res["status"] == "ok" and res["out"]["passed"]
    EVENT_LIST.validate_python(res["events"])  # what the browser stores is valid
    k.add_events(json.dumps(res["events"]))
    snap = json.loads(k.snapshot(TODAY.isoformat()))
    assert snap["progress"]["xp_total"] == 10
    assert json.loads(k.exercise(QUIZ))["passed"] is True


def test_kernel_quests_view(k: Any, fakes: None) -> None:
    plan = {"day": TODAY.isoformat(), "items": [[0, QUIZ], [1, ROOT[0]]]}
    res = json.loads(k.submit(_req(quest_plan=plan["items"])))
    k.add_events(json.dumps(res["events"]))
    board = json.loads(k.quests(json.dumps(plan)))
    assert [i["completed"] for i in board["items"]] == [True, False]


def test_kernel_grading_inputs(k: Any) -> None:
    assert "solution_sql" in json.loads(k.grading_inputs("sql-first-look"))
    assert "hidden_tests" in json.loads(k.grading_inputs("py-typed-position"))
    assert k.grading_inputs(QUIZ) == "null"


def test_xp_events_dedupe_by_key_in_kernel(k: Any, fakes: None) -> None:
    a = json.loads(k.submit(_req(device_id="phone")))["events"]
    b = json.loads(k.submit(_req(device_id="ipad")))["events"]
    k.add_events(json.dumps(a + b))
    xp = [e for e in EVENT_LIST.validate_python(a + b) if isinstance(e, XpAwardedEvent)]
    assert len(xp) == 2
    assert json.loads(k.snapshot(TODAY.isoformat()))["progress"]["xp_total"] == 10
