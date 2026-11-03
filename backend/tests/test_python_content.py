"""Every Python exercise must be solvable and not already solved.

The reference solution has to pass all visible and hidden tests, and the starter code has to
fail at least one hidden test. Runs in CPython with the backend's packages; the browser runs
the same harness in Pyodide (see docs/notes/m2-pyodide-spike.md for version skew).
"""

import pytest

from app.config import get_settings
from app.content.loader import load_content
from app.content.schema import PythonExercise
from app.grading.python import declared_test_names
from app.pyrunner.harness import run_tests

# Polars notes it can't verify sortedness when join_asof uses `by=` groups; the exercise sorts.
pytestmark = pytest.mark.filterwarnings("ignore:Sortedness of columns cannot be checked")

BUNDLE = load_content(get_settings().content_dir)
PY_EXERCISES = [
    ex
    for nodes in BUNDLE.nodes.values()
    for n in nodes
    for ex in n.exercises
    if isinstance(ex, PythonExercise)
]


def _failures(report: dict[str, object]) -> list[str]:
    tests = report["tests"]
    assert isinstance(tests, list)
    return [f"{t['name']}: {t['error']}" for t in tests if not t["passed"]]


@pytest.mark.parametrize("ex", PY_EXERCISES, ids=lambda e: e.slug)
async def test_solution_passes_everything(ex: PythonExercise) -> None:
    for label, tests in (("visible", ex.visible_tests), ("hidden", ex.hidden_tests)):
        if not tests.strip():
            continue
        r = await run_tests(ex.solution, tests, list(ex.packages))
        assert r["setup_error"] is None, f"{label}: {r['setup_error']}"
        assert {t["name"] for t in r["tests"]} == declared_test_names(tests)
        assert not _failures(r), f"{label} tests failed: {_failures(r)}"


@pytest.mark.parametrize("ex", PY_EXERCISES, ids=lambda e: e.slug)
async def test_starter_code_fails_a_hidden_test(ex: PythonExercise) -> None:
    r = await run_tests(ex.starter_code, ex.hidden_tests, list(ex.packages))
    assert r["setup_error"] is not None or _failures(r), "starter code already passes"
