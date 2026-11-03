"""The Pyodide test harness, exercised in CPython (it's the same file the browser loads)."""

from typing import Any

from app.pyrunner.harness import MAX_OUTPUT_CHARS, collect_tests, run_tests

ADD = "def add(a, b):\n    return a + b\n"


async def _run(user: str, tests: str, packages: list[str] | None = None) -> dict[str, Any]:
    return await run_tests(user, tests, packages)


async def test_passing_and_failing_tests_reported_in_order() -> None:
    tests = (
        "from solution import add\n"
        "def test_ok():\n    assert add(1, 2) == 3\n"
        "def test_bad():\n    got = add(1, 1)\n    assert got == 3\n"
    )
    r = await _run(ADD, tests)
    assert r["setup_error"] is None
    assert [(t["name"], t["passed"]) for t in r["tests"]] == [
        ("test_ok", True),
        ("test_bad", False),
    ]
    err = r["tests"][1]["error"]
    assert "assert got == 3" in err  # bare assert → failing line shown
    assert "got=2" in err  # locals shown
    assert "tests.py:6" in err


async def test_assert_message_wins_over_source_line() -> None:
    r = await _run(ADD, "def test_x():\n    assert False, 'custom msg'\n")
    assert "AssertionError: custom msg" in r["tests"][0]["error"]


async def test_exception_in_user_code_points_at_solution() -> None:
    user = "def add(a, b):\n    return a + undefined_name\n"
    r = await _run(user, "from solution import add\ndef test_x():\n    add(1, 2)\n")
    err = r["tests"][0]["error"]
    assert "NameError" in err and "solution.py:2" in err


async def test_syntax_error_is_setup_error() -> None:
    r = await _run("def add(a, b)\n    return a\n", "def test_x():\n    pass\n")
    assert r["tests"] == []
    assert r["setup_error"].startswith("SyntaxError")
    assert "solution.py:1" in r["setup_error"]


async def test_stdout_is_captured_per_test() -> None:
    user = "print('loading')\ndef f():\n    print('inside f')\n    return 1\n"
    tests = "from solution import f\ndef test_a():\n    f()\ndef test_b():\n    pass\n"
    r = await _run(user, tests)
    assert r["setup_stdout"] == "loading\n"
    assert r["tests"][0]["stdout"] == "inside f\n"
    assert r["tests"][1]["stdout"] == ""


async def test_runaway_output_is_capped() -> None:
    r = await _run("", "def test_spam():\n    for _ in range(100_000):\n        print('x' * 10)\n")
    out = r["tests"][0]["stdout"]
    assert len(out) < MAX_OUTPUT_CHARS + 100
    assert out.endswith("output truncated")


async def test_async_tests_are_awaited() -> None:
    tests = "import asyncio\nasync def test_a():\n    await asyncio.sleep(0)\n    assert False\n"
    r = await _run("", tests)
    assert r["tests"][0]["passed"] is False  # proves the coroutine actually ran


async def test_player_cannot_inject_tests() -> None:
    user = ADD + "def test_free_pass():\n    pass\n"
    tests = "from solution import *\ndef test_real():\n    assert add(2, 2) == 4\n"
    r = await _run(user, tests)
    assert [t["name"] for t in r["tests"]] == ["test_real"]


async def test_system_exit_in_a_test_does_not_stop_the_run() -> None:
    tests = "import sys\ndef test_a():\n    sys.exit(1)\ndef test_b():\n    pass\n"
    r = await _run("", tests)
    assert [t["passed"] for t in r["tests"]] == [False, True]


async def test_fresh_solution_module_each_run() -> None:
    await _run("X = 1\n", "def test_a():\n    pass\n")
    r = await _run(
        "Y = 2\n", "import solution\ndef test_a():\n    assert not hasattr(solution, 'X')\n"
    )
    assert r["tests"][0]["passed"]


async def test_fastapi_shim_runs_sync_dependencies() -> None:
    user = (
        "from fastapi import Depends, FastAPI\n"
        "app = FastAPI()\n"
        "def get_n():\n    return 41\n"
        "@app.get('/n')\ndef n(v: int = Depends(get_n)):\n    return {'n': v + 1}\n"
    )
    tests = (
        "import httpx\nfrom solution import app\n"
        "async def test_n():\n"
        "    t = httpx.ASGITransport(app=app)\n"
        "    async with httpx.AsyncClient(transport=t, base_url='http://t') as c:\n"
        "        assert (await c.get('/n')).json() == {'n': 42}\n"
    )
    r = await _run(user, tests, ["fastapi", "httpx"])
    assert r["tests"][0]["passed"], r["tests"][0]["error"]


def test_collect_tests_rules() -> None:
    ns: dict[str, Any] = {"__name__": "tests"}
    exec(
        "from os.path import join as test_imported\n"
        "test_data = [1, 2]\n"
        "class test_klass: pass\n"
        "def helper(): pass\n"
        "def test_b(): pass\n"
        "async def test_a(): pass\n",
        ns,
    )
    assert [n for n, _ in collect_tests(ns)] == ["test_b", "test_a"]


async def test_multiline_locals_are_collapsed() -> None:
    tests = "def test_x():\n    table = 'shape: (5, 4)\\nrow1\\nrow2'\n    assert False\n"
    r = await _run("", tests)
    assert "table='shape: (5, 4)\\nrow1\\nrow2'" in r["tests"][0]["error"]  # str repr is 1 line

    class Frame:
        def __repr__(self) -> str:
            return "shape: (5, 4)\nrow1\nrow2"

    from app.pyrunner.harness import _short_repr

    assert _short_repr(Frame()) == "shape: (5, 4) …"
