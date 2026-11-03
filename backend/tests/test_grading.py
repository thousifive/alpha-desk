from datetime import date, datetime
from decimal import Decimal

import pytest

from app.config import get_settings
from app.grading.sql import _expected_cached, expected_result, normalize_value


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        (True, True),
        (3, 3),
        (1.5, 1.5),
        ("x", "x"),
        (date(2025, 1, 2), "2025-01-02"),
        (datetime(2025, 1, 2, 0, 0), "2025-01-02T00:00:00"),
        (datetime(2025, 1, 2, 9, 30, 0, 123), "2025-01-02T09:30:00.000123"),
        (Decimal("1.25"), 1.25),
    ],
)
def test_normalize_value(raw: object, expected: object) -> None:
    got = normalize_value(raw)
    assert got == expected
    assert type(got) is type(expected)


async def test_expected_result_runs_off_loop_and_caches() -> None:
    _expected_cached.cache_clear()
    sql = "SELECT ticker, listed_on FROM tickers ORDER BY ticker LIMIT 2"
    first = await expected_result(get_settings().dataset_dir, sql)
    second = await expected_result(get_settings().dataset_dir, sql)
    assert first is second  # cached
    assert first.columns == ["ticker", "listed_on"]
    assert isinstance(first.rows[0][1], str)  # DATE normalized to ISO string
