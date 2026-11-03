from typing import Any

import pytest
from httpx import AsyncClient

from app.config import get_settings
from app.content.loader import load_content, sync_content
from app.content.schema import SqlExercise
from app.db import get_sessionmaker
from app.grading.sql import _expected_cached

BUNDLE = load_content(get_settings().content_dir)


@pytest.fixture(autouse=True)
async def _synced() -> None:
    async with get_sessionmaker()() as s:
        await sync_content(s, BUNDLE)


def _sql_ex(slug: str) -> SqlExercise:
    ex = next(e for n in BUNDLE.nodes["sql-olap"] for e in n.exercises if e.slug == slug)
    assert isinstance(ex, SqlExercise)
    return ex


def _browser_result(sql: str) -> dict[str, Any]:
    """What the frontend would POST after running `sql` in DuckDB-WASM."""
    rs = _expected_cached(get_settings().dataset_dir, sql)
    return {"columns": rs.columns, "rows": rs.rows}


# ---- always-on behaviour ---------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/api/progress",
        "/api/branches",
        "/api/branches/sql-olap",
        "/api/exercises/sql-first-look",
        "/api/datasets/meridian/prices.parquet",
    ],
)
async def test_routes_require_auth(client: AsyncClient, path: str) -> None:
    assert (await client.get(path)).status_code == 401


async def test_branches_list(authed_client: AsyncClient) -> None:
    branches = (await authed_client.get("/api/branches")).json()
    assert branches[0]["id"] == "sql-olap"
    sql = branches[0]
    assert sql["playable"] is True
    assert sql["n_exercises"] >= 15
    assert sql["n_passed"] == 0
    assert sql["boss"]["title"]


async def test_branch_detail_states(authed_client: AsyncClient) -> None:
    body = (await authed_client.get("/api/branches/sql-olap")).json()
    states = {n["slug"]: n["state"] for n in body["nodes"]}
    assert states["select-filter"] == "available"
    assert states["joins"] == "locked"
    assert (await authed_client.get("/api/branches/nope")).status_code == 404


async def test_exercise_hides_solution(authed_client: AsyncClient) -> None:
    resp = await authed_client.get("/api/exercises/sql-first-look")
    assert resp.status_code == 200
    body = resp.json()
    assert body["persona"] == "marcus"
    assert body["next_slug"] == "sql-tech-roster"
    text = resp.text.lower()
    assert "solution" not in text and "order_sensitive" not in text


async def test_quiz_hides_answer(authed_client: AsyncClient) -> None:
    body = (await authed_client.get("/api/exercises/quiz-columnar-scan")).json()
    assert len(body["choices"]) == 4
    assert "answer" not in body and "explanation" not in body


async def test_locked_node_rejects_attempts(authed_client: AsyncClient) -> None:
    ex = _sql_ex("sql-close-with-sector")  # in "joins", locked for a fresh player
    resp = await authed_client.post(
        f"/api/exercises/{ex.slug}/attempts",
        json={"code": "", "result": _browser_result(ex.solution_sql)},
    )
    assert resp.status_code == 403


async def test_sql_attempt_requires_result(authed_client: AsyncClient) -> None:
    resp = await authed_client.post("/api/exercises/sql-first-look/attempts", json={"code": "x"})
    assert resp.status_code == 422


async def test_dataset_download_allow_list(authed_client: AsyncClient) -> None:
    ok = await authed_client.get("/api/datasets/meridian/prices.parquet")
    assert ok.status_code == 200
    assert ok.content[:4] == b"PAR1"  # Parquet magic bytes
    assert (await authed_client.get("/api/datasets/meridian/secrets.parquet")).status_code == 404


async def test_progress_shape(authed_client: AsyncClient) -> None:
    body = (await authed_client.get("/api/progress")).json()
    assert body["xp_total"] == 0
    assert body["passed_exercises"] == 0
    assert body["playable_exercises"] >= 15
    assert body["next_boss"]["branch_id"] == "sql-olap"
    # level is null until TODO(me) #1 is done, then {"title": "Intern", ...}
    assert body["level"] is None or body["level"]["title"] == "Intern"


# ---- needs TODO(me) #1-#3 -------------------------------------------------------------

needs_todos = pytest.mark.xfail(
    reason="needs TODO(me) #1 level_for_xp, #2 xp_for_attempt, #3 compare_result_sets",
    strict=True,
)


@needs_todos
async def test_solving_a_ticket_awards_xp_once(authed_client: AsyncClient) -> None:
    ex = _sql_ex("sql-first-look")
    url = f"/api/exercises/{ex.slug}/attempts"
    payload = {"code": ex.solution_sql, "result": _browser_result(ex.solution_sql)}

    first = (await authed_client.post(url, json=payload)).json()
    assert first["passed"] is True
    assert first["xp_awarded"] == 25  # difficulty 1 + first-try bonus
    assert first["level_after"]["title"] == "Intern"

    again = (await authed_client.post(url, json=payload)).json()
    assert again["passed"] is True
    assert again["already_passed"] is True
    assert again["xp_awarded"] == 0
    assert again["xp_total"] == first["xp_total"]


@needs_todos
async def test_wrong_answer_fails_then_pass_without_bonus(authed_client: AsyncClient) -> None:
    ex = _sql_ex("sql-first-look")
    url = f"/api/exercises/{ex.slug}/attempts"
    wrong = _browser_result(ex.solution_sql)
    wrong["rows"] = wrong["rows"][:5]
    bad = (await authed_client.post(url, json={"code": "", "result": wrong})).json()
    assert bad["passed"] is False
    assert "row" in bad["feedback"].lower()

    good = {"code": "", "result": _browser_result(ex.solution_sql)}
    ok = (await authed_client.post(url, json=good)).json()
    assert ok["passed"] is True
    assert ok["xp_awarded"] == 20  # no first-try bonus


@needs_todos
async def test_mastering_node_unlocks_next_and_pays_bonus(authed_client: AsyncClient) -> None:
    node = next(n for n in BUNDLE.nodes["sql-olap"] if n.slug == "select-filter")
    last: dict[str, Any] = {}
    for ex in node.exercises:
        assert isinstance(ex, SqlExercise)
        resp = await authed_client.post(
            f"/api/exercises/{ex.slug}/attempts",
            json={"code": "", "result": _browser_result(ex.solution_sql)},
        )
        last = resp.json()
    assert last["node_bonus_xp"] == node.xp_reward
    detail = (await authed_client.get("/api/branches/sql-olap")).json()
    states = {n["slug"]: n["state"] for n in detail["nodes"]}
    assert states["select-filter"] == "mastered"
    assert states["joins"] == "available"


@needs_todos
async def test_level_up_reported(authed_client: AsyncClient) -> None:
    order = ["select-filter", "joins", "aggregation", "ctes", "window-lag"]
    leveled = False
    for node_slug in order:
        node = next(n for n in BUNDLE.nodes["sql-olap"] if n.slug == node_slug)
        for ex in node.exercises:
            assert isinstance(ex, SqlExercise)
            r = (
                await authed_client.post(
                    f"/api/exercises/{ex.slug}/attempts",
                    json={"code": "", "result": _browser_result(ex.solution_sql)},
                )
            ).json()
            assert r["passed"], ex.slug
            if r["level_before"]["index"] < r["level_after"]["index"]:
                leveled = True
                assert r["level_after"]["title"] == "Analyst"
    assert leveled
    assert (await authed_client.get("/api/progress")).json()["level"]["title"] == "Analyst"
