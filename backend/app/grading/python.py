"""Server side of Python grading.

The browser runs the hidden tests in Pyodide and posts one outcome per test. The server
can't re-run them (no sandbox in M2; see docs/notes/m2-pyodide-spike.md), so its job is to
check that the report is *about the right tests*: every hidden test reported exactly once,
nothing extra, all passed. This is the same trust model as SQL in M1, where the browser
posts the result set and the server compares it.
"""

import ast
from dataclasses import dataclass


def declared_test_names(source: str) -> set[str]:
    """Names of top-level `def test_*` / `async def test_*` functions in `source`.

    Uses `ast` (parse only, never execute), so it's safe on any content and matches what the
    harness's collect_tests() finds at runtime for well-formed test files.
    """
    tree = ast.parse(source)
    return {
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and node.name.startswith("test_")
    }


@dataclass(frozen=True)
class ReportedTest:
    name: str
    passed: bool


@dataclass(frozen=True)
class PythonGrade:
    passed: bool
    reason: str  # shown to the player; "" when passed


def grade_python_report(expected: set[str], reported: list[ReportedTest]) -> PythonGrade:
    """Decide pass/fail from the browser's per-test report.

    Rules, checked in this order (first failure wins):
    1. A name reported more than once → fail, reason mentions "duplicate" and the name(s).
    2. Hidden tests missing from the report → fail, reason mentions "missing" and lists them
       sorted. (A stale browser tab with old tests ends up here.)
    3. Names that aren't hidden tests → fail, reason mentions "unknown" and lists them sorted.
    4. Any reported test with passed=False → fail with reason "<n> of <total> tests failed:
       name_a, name_b" (failed names sorted).
    5. Otherwise → PythonGrade(passed=True, reason="").

    TODO(me): implement.
    Teaches: validating untrusted client input, set algebra (-, &, |), collections.Counter.
    """
    raise NotImplementedError("TODO(me) #3: grade_python_report")
