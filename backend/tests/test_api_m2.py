"""M2 API: Python exercises, daily quests, streaks.

Most of these run with *fakes* for the open TODO(me) functions, so the wiring around them is
tested today. The fakes are deliberately dumb (fixed values, top-k instead of random) and
aren't reference implementations. End-to-end tests that need the real TODOs are strict xfail.
"""

import random
from collections.abc import Sequence
from datetime import date
from typing import Any

import pytest
from httpx import AsyncClient

import app.game.daily as daily
import app.game.quests as quests
import app.routers.exercises as exercises
from app.config import get_settings
from app.content.loader import load_content, sync_content
from app.content.schema import PythonExercise
from app.db import get_sessionmaker
from app.game.streaks import StreakState
from app.grading.python import PythonGrade
from app.grading.sql import Comparison

BUNDLE = load_content(get_settings().content_dir)
PY_SLUG = "polars-daily-returns"


@pytest.fixture(autouse=True)
async def _synced() -> None:
    async with get_sessionmaker()() as s:
        await sync_content(s, BUNDLE)


@pytest.fixture
def m2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "current_milestone", "M2")


def _top_k[T](items: Sequence[T], weights: Sequence[float], k: int, rng: random.Random) -> list[T]:
    ranked = sorted(range(len(items)), key=lambda i: -weights[i])
    return [items[i] for i in ranked[: max(k, 0)]]


STREAK_RUN_START = date(2026, 1, 1)


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch, m2: None) -> None:
    monkeypatch.setattr(quests, "weighted_sample", _top_k)
    monkeypatch.setattr(exercises, "xp_for_attempt", lambda *_a, **_k: 10)
    monkeypatch.setattr(
        exercises, "compare_result_sets", lambda *_a, **_k: Comparison(passed=True, reason="")
    )
    monkeypatch.setattr(exercises, "grade_python_report", lambda *_: PythonGrade(True, ""))
    # A fixed 7-day streak that's active today: enough to exercise milestone payouts.
    monkeypatch.setattr(
        daily, "compute_streak", lambda *_: StreakState(7, 7, 1, True, STREAK_RUN_START)
    )


def _py() -> PythonExercise:
    ex = next(
        e for ns in BUNDLE.nodes.values() for n in ns for e in n.exercises if e.slug == PY_SLUG
    )
    assert isinstance(ex, PythonExercise)
    return ex


def _payload(slug: str) -> dict[str, Any]:
    """A plausible passing submission for any exercise type (graders are faked)."""
    ex = next(e for ns in BUNDLE.nodes.values() for n in ns for e in n.exercises if e.slug == slug)
    match ex.type:
        case "sql":
            return {"code": "", "result": {"columns": ["x"], "rows": [[1]]}}
        case "quiz":
            return {"code": "", "choice": 0}
        case _:
            return {"code": "", "tests": [{"name": "test_x", "passed": True}]}


# ---- always on ------------------------------------------------------------------------


async def test_python_exercise_hides_hidden_tests(authed_client: AsyncClient, m2: None) -> None:
    body = (await authed_client.get(f"/api/exercises/{PY_SLUG}")).json()
    assert body["type"] == "python"
    assert body["packages"] == ["polars"]
    assert "def test_single_ticker" in body["visible_tests"]
    text = str(body)
    assert "test_returns_are_per_ticker" not in text  # a hidden test name
    assert ".over(" not in text  # from the reference solution


async def test_test_bundle_serves_hidden_tests(authed_client: AsyncClient, m2: None) -> None:
    resp = await authed_client.post(f"/api/exercises/{PY_SLUG}/test-bundle")
    assert resp.status_code == 200
    assert resp.json()["hidden_tests"] == _py().hidden_tests


async def test_test_bundle_rules(authed_client: AsyncClient) -> None:
    # Default milestone in tests is the config default; force M1 to prove the gate.
    get_settings().current_milestone, old = "M1", get_settings().current_milestone
    try:
        locked = await authed_client.post(f"/api/exercises/{PY_SLUG}/test-bundle")
        assert locked.status_code == 403
    finally:
        get_settings().current_milestone = old
    not_py = await authed_client.post("/api/exercises/sql-first-look/test-bundle")
    assert not_py.status_code == 404


async def test_python_attempt_requires_tests(authed_client: AsyncClient, m2: None) -> None:
    resp = await authed_client.post(f"/api/exercises/{PY_SLUG}/attempts", json={"code": "x"})
    assert resp.status_code == 422


async def test_quests_offline_until_weighted_sample(authed_client: AsyncClient, m2: None) -> None:
    resp = await authed_client.get("/api/quests/today")
    assert resp.status_code == 501
    assert "M2-2" in resp.json()["detail"]


async def test_streak_null_until_compute_streak(authed_client: AsyncClient) -> None:
    assert (await authed_client.get("/api/progress")).json()["streak"] is None


async def test_quests_require_auth(client: AsyncClient) -> None:
    assert (await client.get("/api/quests/today")).status_code == 401


# ---- with fakes for the open TODO(me)s ------------------------------------------------


async def test_today_quests_are_generated_once(authed_client: AsyncClient, fakes: None) -> None:
    first = (await authed_client.get("/api/quests/today")).json()
    assert len(first["items"]) == 3
    assert len({i["branch_id"] for i in first["items"]}) >= 2  # spread over branches
    assert all(not i["completed"] for i in first["items"])
    assert first["est_minutes"] == sum(i["minutes"] for i in first["items"])
    again = (await authed_client.get("/api/quests/today")).json()
    assert again == first


async def test_completing_quests_pays_once_and_bonus_at_the_end(
    authed_client: AsyncClient, fakes: None
) -> None:
    items = (await authed_client.get("/api/quests/today")).json()["items"]
    first = items[0]["slug"]
    url = f"/api/exercises/{first}/attempts"

    out = (await authed_client.post(url, json=_payload(first))).json()
    assert out["passed"] and out["quest_position"] == items[0]["position"]
    assert out["quest_xp"] == 15
    assert not out["quests_all_done"]

    again = (await authed_client.post(url, json=_payload(first))).json()
    assert again["quest_xp"] == 0 and again["quest_position"] is None

    last: dict[str, Any] = {}
    for it in items[1:]:
        last = (
            await authed_client.post(
                f"/api/exercises/{it['slug']}/attempts", json=_payload(it["slug"])
            )
        ).json()
        assert last["passed"], it
    assert last["quests_all_done"] is True
    assert last["quest_xp"] == 15 + 30

    board = (await authed_client.get("/api/quests/today")).json()
    assert board["done"] and all(i["completed"] for i in board["items"])


async def test_failed_attempt_does_not_complete_quest(
    authed_client: AsyncClient, fakes: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(exercises, "grade_python_report", lambda *_: PythonGrade(False, "nope"))
    monkeypatch.setattr(
        exercises, "compare_result_sets", lambda *_a, **_k: Comparison(passed=False, reason="no")
    )
    items = (await authed_client.get("/api/quests/today")).json()["items"]
    slug = next(i["slug"] for i in items if i["type"] in ("python", "sql"))
    out = (await authed_client.post(f"/api/exercises/{slug}/attempts", json=_payload(slug))).json()
    assert out["passed"] is False and out["quest_position"] is None and out["streak"] is None


async def test_streak_milestone_pays_once_per_run(authed_client: AsyncClient, fakes: None) -> None:
    url = "/api/exercises/sql-first-look/attempts"
    first = (await authed_client.post(url, json=_payload("sql-first-look"))).json()
    assert first["streak"]["current"] == 7
    assert first["streak"]["next_milestone"] == 14
    assert first["streak_xp"] == 50
    second = (await authed_client.post(url, json=_payload("sql-first-look"))).json()
    assert second["streak_xp"] == 0
    assert (await authed_client.get("/api/progress")).json()["streak"]["current"] == 7


async def test_xp_total_matches_ledger(authed_client: AsyncClient, fakes: None) -> None:
    from sqlmodel import func, select

    from app.models import XpEvent

    for it in (await authed_client.get("/api/quests/today")).json()["items"]:
        await authed_client.post(f"/api/exercises/{it['slug']}/attempts", json=_payload(it["slug"]))
    xp_total = (await authed_client.get("/api/progress")).json()["xp_total"]
    async with get_sessionmaker()() as s:
        assert (await s.exec(select(func.sum(XpEvent.amount)))).one() == xp_total


# ---- end to end, needs the real TODO(me)s ---------------------------------------------

needs_todos = pytest.mark.xfail(
    reason="needs TODO(me) #2 xp_for_attempt and M2-3 grade_python_report", strict=True
)


@needs_todos
async def test_python_submit_end_to_end(authed_client: AsyncClient, m2: None) -> None:
    from app.grading.python import declared_test_names

    names = sorted(declared_test_names(_py().hidden_tests))
    url = f"/api/exercises/{PY_SLUG}/attempts"
    bad = [{"name": n, "passed": i != 0} for i, n in enumerate(names)]
    fail = (await authed_client.post(url, json={"code": "", "tests": bad})).json()
    assert fail["passed"] is False and names[0] in fail["feedback"]

    good = [{"name": n, "passed": True} for n in names]
    ok = (await authed_client.post(url, json={"code": "", "tests": good})).json()
    assert ok["passed"] is True and ok["xp_awarded"] == 20  # difficulty 1, not first try
