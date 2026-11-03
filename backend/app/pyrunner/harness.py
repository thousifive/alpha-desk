"""A tiny pytest-style runner that works in both CPython and Pyodide.

The *same file* is loaded into the browser's Pyodide worker (Vite imports it as a raw string)
and imported by the backend's content tests, so the code that grades the player in the
browser is the code pytest covers here.

Stdlib only, and nothing newer than Python 3.12 (the browser has 3.14, the backend 3.12).

Execution model:
- The player's code is exec'd into a fresh module registered as `solution`, so tests say
  `from solution import daily_returns` like they would against a real file.
- Test code is exec'd into its own namespace (module name `tests`). Tests are collected only
  from there, so the player can't inject extra passing tests from their own code.
- Each test gets its own captured stdout. `async def` tests are awaited, which is how
  FastAPI tests run (httpx.AsyncClient + ASGITransport; TestClient needs threads).
"""

import inspect
import io
import json
import sys
import time
import traceback
import types
from collections.abc import Callable
from contextlib import redirect_stdout
from typing import Any

MAX_OUTPUT_CHARS = 64_000
MAX_REPR_CHARS = 200
SOLUTION_FILE = "solution.py"
TESTS_FILE = "tests.py"


class _CappedIO(io.StringIO):
    """StringIO that stops storing after MAX_OUTPUT_CHARS, so `while True: print()` in a
    test can't balloon the worker's memory before the timeout kills it."""

    def __init__(self) -> None:
        super().__init__()
        self.truncated = False

    def write(self, s: str) -> int:
        room = MAX_OUTPUT_CHARS - self.tell()
        if room <= 0:
            self.truncated = True
            return len(s)  # pretend we wrote it; print() would raise otherwise
        if len(s) > room:
            self.truncated = True
            super().write(s[:room])
            return len(s)
        return super().write(s)

    def text(self) -> str:
        return self.getvalue() + ("\n… output truncated" if self.truncated else "")


def install_fastapi_shim() -> None:
    """Make FastAPI work without threads (Pyodide can't start any).

    Starlette runs sync endpoints/dependencies via anyio.to_thread. We swap that helper for
    one that just calls the function inline. Each module did `from ... import
    run_in_threadpool`, which copied the name into its own namespace, so we patch every copy.
    """

    async def _inline(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)

    for name in (
        "starlette.concurrency",
        "fastapi.concurrency",
        "fastapi.routing",
        "fastapi.dependencies.utils",
    ):
        mod = __import__(name, fromlist=["_"])
        if hasattr(mod, "run_in_threadpool"):
            mod.run_in_threadpool = _inline  # type: ignore[attr-defined]


def collect_tests(namespace: dict[str, Any]) -> list[tuple[str, Callable[..., Any]]]:
    """Test functions defined in `namespace`, in definition order.

    A test is a function (sync or async) whose name starts with `test_` and that was
    *defined* in this namespace: `from solution import test_helper` doesn't count, because an
    imported function's __module__ is the module it came from.
    """
    module_name = namespace.get("__name__")
    return [
        (name, obj)
        # dicts keep insertion order (guaranteed since 3.7), which is definition order here.
        for name, obj in namespace.items()
        if name.startswith("test_")
        and inspect.isfunction(obj)  # True for `async def` too; False for classes/lambdas-in-lists
        and obj.__module__ == module_name
    ]


def _short_repr(value: Any) -> str:
    try:
        r = repr(value)
    except Exception:  # a broken __repr__ shouldn't break the report
        r = f"<unrepresentable {type(value).__name__}>"
    if "\n" in r:  # tables (DataFrames) print as many lines; one is enough inline
        r = r.splitlines()[0] + " …"
    return r if len(r) <= MAX_REPR_CHARS else r[: MAX_REPR_CHARS - 1] + "…"


def _source_line(filename: str, lineno: int, sources: dict[str, str]) -> str:
    lines = sources.get(filename, "").splitlines()
    return lines[lineno - 1].strip() if 0 < lineno <= len(lines) else ""


def describe_failure(exc: BaseException, sources: dict[str, str]) -> str:
    """Human-readable failure: the traceback trimmed to our two files, plus, for a bare
    `assert`, the failing line and the test's local variables (a poor man's pytest rewrite)."""
    frames = [f for f in traceback.extract_tb(exc.__traceback__) if f.filename in sources]
    parts: list[str] = []
    if isinstance(exc, AssertionError):
        last = frames[-1] if frames else None
        line = _source_line(last.filename, last.lineno or 0, sources) if last else ""
        parts.append(f"AssertionError: {exc}" if str(exc) else f"AssertionError: {line}")
        # Walk to the innermost frame inside tests.py to show what the test saw.
        tb = exc.__traceback__
        test_locals: dict[str, Any] = {}
        while tb is not None:
            if tb.tb_frame.f_code.co_filename == TESTS_FILE:
                test_locals = tb.tb_frame.f_locals
            tb = tb.tb_next
        shown = {k: v for k, v in test_locals.items() if not k.startswith("_")}
        if shown:
            parts.append("locals: " + ", ".join(f"{k}={_short_repr(v)}" for k, v in shown.items()))
    else:
        parts.append("".join(traceback.format_exception_only(exc)).strip())
    if frames:
        parts.append("at " + " → ".join(f"{f.filename}:{f.lineno} in {f.name}" for f in frames))
    return "\n".join(parts)


async def run_tests(
    user_code: str, test_code: str, packages: list[str] | None = None
) -> dict[str, Any]:
    """Run `test_code` against `user_code`. Never raises for player mistakes; everything
    ends up in the returned report (a JSON-ready dict)."""
    packages = packages or []
    if "fastapi" in packages:
        install_fastapi_shim()
    sources = {SOLUTION_FILE: user_code, TESTS_FILE: test_code}
    report: dict[str, Any] = {"setup_error": None, "setup_stdout": "", "tests": []}

    solution = types.ModuleType("solution")
    solution.__file__ = SOLUTION_FILE
    sys.modules["solution"] = solution  # so `from solution import x` finds *this* run's code
    tests_ns: dict[str, Any] = {"__name__": "tests", "__file__": TESTS_FILE}

    out = _CappedIO()
    try:
        with redirect_stdout(out):
            # compile() with a filename makes tracebacks say "solution.py:12", not "<string>".
            exec(compile(user_code, SOLUTION_FILE, "exec"), solution.__dict__)
            exec(compile(test_code, TESTS_FILE, "exec"), tests_ns)
    except BaseException as e:  # SyntaxError, NameError at import time, SystemExit, …
        report["setup_error"] = (
            describe_failure(e, sources)
            if not isinstance(e, SyntaxError)
            else _describe_syntax_error(e)
        )
        report["setup_stdout"] = out.text()
        return report
    report["setup_stdout"] = out.text()

    for name, fn in collect_tests(tests_ns):
        out = _CappedIO()
        error: str | None = None
        start = time.perf_counter()
        try:
            with redirect_stdout(out):
                result = fn()
                if inspect.isawaitable(result):
                    await result
        except BaseException as e:  # catch SystemExit too: one test must not end the run
            error = describe_failure(e, sources)
        report["tests"].append(
            {
                "name": name,
                "passed": error is None,
                "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                "stdout": out.text(),
                "error": error,
            }
        )
    return report


def _describe_syntax_error(e: SyntaxError) -> str:
    where = f"{e.filename}:{e.lineno}" if e.lineno else str(e.filename)
    caret = ""
    if e.text and e.offset:
        caret = f"\n    {e.text.rstrip()}\n    {' ' * (e.offset - 1)}^"
    return f"SyntaxError: {e.msg} ({where}){caret}"


async def run_tests_json(user_code: str, test_code: str, packages_json: str = "[]") -> str:
    """Entry point for the browser worker: strings in, JSON string out (no proxy objects)."""
    return json.dumps(await run_tests(user_code, test_code, json.loads(packages_json)))
