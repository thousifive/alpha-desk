"""Tests for TODO(me) #4: app.dataset.generate.validate_ohlcv.

Remove the `pytestmark` line once you've implemented it; xfail is strict, so passing
tests will fail the run until you do (that's the signal you're done).
"""

from datetime import date

import polars as pl
import pytest

from app.dataset.generate import validate_ohlcv

pytestmark = pytest.mark.xfail(reason="TODO(me): implement validate_ohlcv", strict=True)


def _frame(**overrides: list[object]) -> pl.DataFrame:
    base: dict[str, list[object]] = {
        "date": [date(2024, 1, 2), date(2024, 1, 2), date(2024, 1, 3)],
        "ticker": ["AAA", "BBB", "AAA"],
        "open": [10.0, 20.0, 10.5],
        "high": [11.0, 21.0, 11.0],
        "low": [9.5, 19.0, 10.0],
        "close": [10.5, 20.5, 10.8],
        "volume": [1000, 2000, 1500],
    }
    base.update(overrides)
    return pl.DataFrame(base)


def test_valid_frame_passes() -> None:
    validate_ohlcv(_frame())  # must not raise


def test_high_below_close_fails() -> None:
    with pytest.raises(ValueError, match="high"):
        validate_ohlcv(_frame(high=[10.2, 21.0, 11.0]))  # close 10.5 > high 10.2


def test_low_above_open_fails() -> None:
    with pytest.raises(ValueError, match="low"):
        validate_ohlcv(_frame(low=[10.1, 19.0, 10.0]))  # open 10.0 < low 10.1


def test_non_positive_volume_fails() -> None:
    with pytest.raises(ValueError, match="volume"):
        validate_ohlcv(_frame(volume=[1000, 0, 1500]))


def test_duplicate_date_ticker_fails() -> None:
    dup = _frame(ticker=["AAA", "AAA", "AAA"], date=[date(2024, 1, 2)] * 2 + [date(2024, 1, 3)])
    with pytest.raises(ValueError, match="duplicate"):
        validate_ohlcv(dup)


def test_error_reports_row_count() -> None:
    with pytest.raises(ValueError, match="2"):
        validate_ohlcv(_frame(volume=[0, 0, 1500]))  # two bad rows → message mentions 2
