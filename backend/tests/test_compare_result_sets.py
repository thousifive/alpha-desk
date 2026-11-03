"""Tests for TODO(me) #3: app.grading.sql.compare_result_sets. Remove `pytestmark` when done.

normalize_value is implemented already; its tests live in test_grading.py.
"""

import pytest

from app.grading.sql import ResultSet, compare_result_sets

pytestmark = pytest.mark.xfail(reason="TODO(me) #3: implement compare_result_sets", strict=True)


def rs(columns: list[str], *rows: list[object]) -> ResultSet:
    return ResultSet(columns=columns, rows=[list(r) for r in rows])  # type: ignore[misc]


EXPECTED = rs(["ticker", "ret"], ["AAA", 0.1], ["BBB", -0.2], ["CCC", None])


def cmp(actual: ResultSet, *, ordered: bool = False, tol: float = 1e-6):  # type: ignore[no-untyped-def]
    return compare_result_sets(actual, EXPECTED, order_sensitive=ordered, float_tol=tol)


def test_identical_passes() -> None:
    result = cmp(EXPECTED, ordered=True)
    assert result.passed
    assert result.mismatch_row is None


def test_column_names_case_insensitive() -> None:
    assert cmp(rs(["TICKER", "Ret"], ["AAA", 0.1], ["BBB", -0.2], ["CCC", None])).passed


def test_wrong_column_name_fails() -> None:
    result = cmp(rs(["ticker", "return"], ["AAA", 0.1], ["BBB", -0.2], ["CCC", None]))
    assert not result.passed
    assert "column" in result.reason.lower()


def test_column_order_matters() -> None:
    result = cmp(rs(["ret", "ticker"], [0.1, "AAA"], [-0.2, "BBB"], [None, "CCC"]))
    assert not result.passed


def test_row_count_mismatch_reports_actual_count() -> None:
    result = cmp(rs(["ticker", "ret"], ["AAA", 0.1]))
    assert not result.passed
    assert "row" in result.reason.lower()
    assert "1" in result.reason


def test_unordered_ignores_row_order_even_with_nulls() -> None:
    shuffled = rs(["ticker", "ret"], ["CCC", None], ["AAA", 0.1], ["BBB", -0.2])
    assert cmp(shuffled).passed


def test_ordered_detects_row_order() -> None:
    shuffled = rs(["ticker", "ret"], ["BBB", -0.2], ["AAA", 0.1], ["CCC", None])
    result = cmp(shuffled, ordered=True)
    assert not result.passed
    assert result.mismatch_row == 0


def test_float_tolerance() -> None:
    close_enough = rs(["ticker", "ret"], ["AAA", 0.1000004], ["BBB", -0.2], ["CCC", None])
    too_far = rs(["ticker", "ret"], ["AAA", 0.11], ["BBB", -0.2], ["CCC", None])
    assert cmp(close_enough).passed
    assert not cmp(too_far).passed


def test_int_and_float_compare_numerically() -> None:
    expected = rs(["n"], [3])
    assert compare_result_sets(
        rs(["n"], [3.0]), expected, order_sensitive=True, float_tol=1e-6
    ).passed


def test_bool_is_not_a_number() -> None:
    expected = rs(["flag"], [True])
    assert not compare_result_sets(
        rs(["flag"], [1]), expected, order_sensitive=True, float_tol=1e-6
    ).passed


def test_none_only_matches_none() -> None:
    result = cmp(rs(["ticker", "ret"], ["AAA", 0.1], ["BBB", -0.2], ["CCC", 0.0]), ordered=True)
    assert not result.passed
    assert result.mismatch_row == 2


def test_reason_does_not_leak_expected_values() -> None:
    result = cmp(rs(["ticker", "ret"], ["AAA", 0.5], ["BBB", -0.2], ["CCC", None]), ordered=True)
    assert not result.passed
    assert "0.1" not in result.reason
