"""Entry points the browser's rules worker calls through Pyodide. JSON strings in, JSON out.

JSON at the boundary (instead of passing Python objects to JavaScript) means no PyProxy
handles leak into JS, and the worker protocol stays plain structured-clone data.

Module-level state is fine here: one worker = one interpreter = one player's device.
CPython tests call the same functions, so the browser path is covered without Pyodide.
"""

import json
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ValidationError

from app.content.schema import ContentBundle, PythonExercise, SqlExercise
from app.events.schema import EVENT_LIST, AnyEvent
from app.game.projection import Derived, project
from app.game.submit import Context, SubmitRejected, decide, grade
from app.grading.sql import ResultSet
from app.schemas import AttemptIn
from app.views import (
    branch_detail,
    branch_summaries,
    exercise_view,
    locate,
    progress_view,
    quest_view,
)

_content: ContentBundle | None = None
_milestone = "M1"
_events: list[AnyEvent] = []
_derived: Derived | None = None  # cache; cleared whenever events change


def _bundle() -> ContentBundle:
    if _content is None:
        raise RuntimeError("load_bundle() first")
    return _content


def _facts() -> Derived:
    global _derived
    if _derived is None:
        _derived = project(_events)
    return _derived


def _dump(obj: BaseModel | None) -> str:
    return "null" if obj is None else obj.model_dump_json()


def load_bundle(bundle_json: str) -> str:
    """bundle_json: the body of GET /api/offline/bundle. Returns its version."""
    global _content, _milestone
    raw = json.loads(bundle_json)
    _content = ContentBundle.model_validate(raw["content"])
    _milestone = raw["milestone"]
    return str(raw["version"])


def reset_events() -> None:
    global _derived
    _events.clear()
    _derived = None


def add_events(events_json: str) -> int:
    """Append a batch (a JSON array of events). Returns how many events the worker holds."""
    global _derived
    # validate_json parses and validates in one pass (in Rust), faster than json.loads first.
    _events.extend(EVENT_LIST.validate_json(events_json))
    _derived = None
    return len(_events)


def snapshot(today: str) -> str:
    """Everything the dashboard and branch pages need, in one call."""
    content = _bundle()
    facts = _facts()
    passed = set(facts.passed)
    details = {b.id: branch_detail(content, b.id, passed, _milestone) for b in content.branches}
    progress = progress_view(
        content,
        passed=passed,
        xp_total=facts.xp_total,
        active_days=facts.active_days,
        today=date.fromisoformat(today),
        milestone=_milestone,
    )
    branches = branch_summaries(content, passed, _milestone)
    return json.dumps(
        {
            "progress": progress.model_dump(mode="json"),
            "branches": [b.model_dump(mode="json") for b in branches],
            "details": {k: v.model_dump(mode="json") for k, v in details.items() if v},
            "event_count": facts.event_count,
        }
    )


def exercise(slug: str) -> str:
    return _dump(exercise_view(_bundle(), slug, set(_facts().passed), _milestone))


def quests(plan_json: str) -> str:
    """plan_json: {"day": "YYYY-MM-DD", "items": [[position, slug], ...]}."""
    plan = json.loads(plan_json)
    day = date.fromisoformat(plan["day"])
    done = {pos for d, pos in _facts().quests_done if d == day}
    items = [(int(p), str(s)) for p, s in plan["items"]]
    return quest_view(_bundle(), day, items, done).model_dump_json()


def submit(request_json: str) -> str:
    """Grade an attempt and return the events to append.

    request: {slug, attempt (AttemptIn), expected?: {columns, rows}, device_id, now (ISO),
    today (YYYY-MM-DD), quest_plan?: [[position, slug], ...]}
    response: {"status": "ok", "out": AttemptOut, "events": [...]}
              {"status": "locked", "message": "TODO(me) ..."}   an open TODO(me) blocks it
              {"status": "rejected", "message": ...}           bad input or a locked node
    """
    req: dict[str, Any] = json.loads(request_json)
    content = _bundle()
    try:
        body = AttemptIn.model_validate(req["attempt"])
        exp = req.get("expected")
        expected = ResultSet(columns=exp["columns"], rows=exp["rows"]) if exp else None
        ctx = Context(
            device_id=req["device_id"],
            now=datetime.fromisoformat(req["now"]),
            today=date.fromisoformat(req["today"]),
            milestone=_milestone,
        )
        plan = req.get("quest_plan")
        verdict = grade(content, req["slug"], body, expected)
        decision = decide(
            content,
            _facts(),
            req["slug"],
            body,
            verdict,
            ctx,
            [(int(p), str(s)) for p, s in plan] if plan is not None else None,
        )
    except NotImplementedError as e:
        # The message carries the TODO(me) id, which the UI maps to its locked panel.
        return json.dumps({"status": "locked", "message": f"Grader offline: {e}"})
    except (SubmitRejected, ValidationError, KeyError, ValueError) as e:
        return json.dumps({"status": "rejected", "message": str(e)})
    return json.dumps(
        {
            "status": "ok",
            "out": decision.out.model_dump(mode="json"),
            "events": [e.model_dump(mode="json") for e in decision.events],
        }
    )


def grading_inputs(slug: str) -> str:
    """What the browser must run before submit: the solution SQL (to compute the expected
    result in DuckDB-WASM) or the hidden Python tests. "null" for quizzes."""
    loc = locate(_bundle(), slug)
    if loc is None:
        return "null"
    match loc.exercise:
        case SqlExercise() as ex:
            return json.dumps({"solution_sql": ex.solution_sql})
        case PythonExercise() as ex:
            return json.dumps({"hidden_tests": ex.hidden_tests})
        case _:
            return "null"
