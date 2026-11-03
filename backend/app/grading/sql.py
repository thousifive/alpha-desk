"""Grade a SQL exercise: compare the result set the browser computed in DuckDB-WASM against
the expected result we compute here with native DuckDB on the same Parquet data.

Normalization contract (the frontend's lib/duckdb/normalize.ts must produce the same):
  DATE       -> "YYYY-MM-DD"
  TIMESTAMP  -> "YYYY-MM-DDTHH:MM:SS" (plus ".ffffff" only if microseconds != 0)
  DECIMAL    -> float
  integers   -> int    (BIGINT/HUGEINT arrive as JS numbers, which is fine at our sizes)
  NULL       -> None
  everything else -> str
"""

import asyncio
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import duckdb

from app.grading.dataset import open_dataset

Cell = str | int | float | bool | None


@dataclass(frozen=True)
class ResultSet:
    columns: list[str]
    rows: list[list[Cell]]


@dataclass(frozen=True)
class Comparison:
    passed: bool
    reason: str = ""  # human-readable, must never reveal expected values
    mismatch_row: int | None = None  # index into the (sorted, if unordered) actual rows


def normalize_value(v: object) -> Cell:
    # Order matters: bool is a subclass of int, and datetime is a subclass of date.
    if v is None or isinstance(v, bool | int | float | str):
        return v  # type: ignore[return-value]  (narrowed by isinstance above)
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return str(v)


def compare_result_sets(
    actual: ResultSet, expected: ResultSet, *, order_sensitive: bool, float_tol: float
) -> Comparison:
    """Decide whether `actual` matches `expected`.

    Rules (the tests in tests/test_compare_result_sets.py pin these down):
      1. Column names must match in order, case-insensitively. Otherwise fail with a
         reason containing "column".
      2. Row counts must match. Otherwise fail with a reason containing "row" that says
         how many rows you returned (don't leak the expected rows themselves).
      3. If not order_sensitive, sort both sides before comparing. Rows can contain None
         and mixed types, so your sort key must never compare None with a number.
      4. Cells: two numbers (int/float, but *not* bool) match when
         math.isclose(a, b, rel_tol=float_tol, abs_tol=float_tol). Everything else
         needs ==. Report the first mismatching row index in `mismatch_row`.

    TODO(me): implement (you'll want `import math`).
    Teaches: dataclasses as return types, sort keys with tuples, and float comparison.
    """
    raise NotImplementedError("TODO(me) #3: compare_result_sets")


# ---------------------------------------------------------------------------------------
# Expected results
# ---------------------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _base_connection(dataset_dir: Path) -> duckdb.DuckDBPyConnection:
    return open_dataset(dataset_dir)


@lru_cache(maxsize=256)
def _expected_cached(dataset_dir: Path, solution_sql: str) -> ResultSet:
    # Keyed on the SQL text itself, so editing a solution in YAML invalidates the cache.
    # .cursor() gives a thread-local handle on the same in-memory database: a DuckDB
    # connection must not be used from two threads at once, but cursors can.
    cur = _base_connection(dataset_dir).cursor()
    try:
        rel = cur.sql(solution_sql)
        cols = list(rel.columns)
        rows = [[normalize_value(v) for v in row] for row in rel.fetchall()]
    finally:
        cur.close()
    return ResultSet(columns=cols, rows=rows)


async def expected_result(dataset_dir: Path, solution_sql: str) -> ResultSet:
    # DuckDB's Python API is blocking C code. Calling it directly inside `async def`
    # would freeze the whole event loop (every request) for the query's duration.
    # to_thread runs it in a worker thread and awaits the result.
    return await asyncio.to_thread(_expected_cached, dataset_dir, solution_sql)
