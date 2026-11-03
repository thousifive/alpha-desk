"""Tests for TODO(me) #3 (M2): app.grading.python.grade_python_report.

Remove the `pytestmark` line once it's implemented; xfail is strict, so passing tests with
the marker still in place fail the run (that's your reminder).
"""

import pytest

from app.grading.python import PythonGrade, ReportedTest, grade_python_report

pytestmark = pytest.mark.xfail(reason="TODO(me) #3: implement grade_python_report", strict=True)

EXPECTED = {"test_a", "test_b", "test_c"}


def _r(*pairs: tuple[str, bool]) -> list[ReportedTest]:
    return [ReportedTest(name=n, passed=p) for n, p in pairs]


def test_all_passed() -> None:
    got = grade_python_report(EXPECTED, _r(("test_a", True), ("test_b", True), ("test_c", True)))
    assert got == PythonGrade(passed=True, reason="")


def test_report_order_does_not_matter() -> None:
    got = grade_python_report(EXPECTED, _r(("test_c", True), ("test_a", True), ("test_b", True)))
    assert got.passed


def test_some_failed_lists_names_sorted() -> None:
    got = grade_python_report(EXPECTED, _r(("test_c", False), ("test_a", False), ("test_b", True)))
    assert not got.passed
    assert got.reason == "2 of 3 tests failed: test_a, test_c"


def test_missing_tests() -> None:
    got = grade_python_report(EXPECTED, _r(("test_a", True)))
    assert not got.passed
    assert "missing" in got.reason and "test_b, test_c" in got.reason


def test_unknown_tests() -> None:
    got = grade_python_report(
        EXPECTED,
        _r(("test_a", True), ("test_b", True), ("test_c", True), ("test_zzz", True)),
    )
    assert not got.passed
    assert "unknown" in got.reason and "test_zzz" in got.reason


def test_duplicates_checked_first() -> None:
    # test_a twice *and* test_c missing: duplicate is reported, not missing.
    got = grade_python_report(EXPECTED, _r(("test_a", True), ("test_a", True), ("test_b", True)))
    assert not got.passed
    assert "duplicate" in got.reason and "test_a" in got.reason


def test_missing_checked_before_failures() -> None:
    got = grade_python_report(EXPECTED, _r(("test_a", False)))
    assert "missing" in got.reason


def test_empty_report_fails() -> None:
    got = grade_python_report(EXPECTED, [])
    assert not got.passed and "missing" in got.reason
