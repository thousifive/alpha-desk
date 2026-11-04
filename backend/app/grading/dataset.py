"""Load the Meridian Parquet files into DuckDB tables with the names the browser uses."""

import hashlib
from functools import lru_cache
from pathlib import Path

import duckdb

TABLES = ("tickers", "prices", "factors", "trades", "positions", "corporate_actions")


def dataset_version(dataset_dir: Path) -> str:
    """A short hash of the parquet files' bytes. The browser puts it in the download URL
    (?v=...), so its service worker can cache the files forever and still notice a re-seed."""
    return _dataset_version(
        dataset_dir, tuple((dataset_dir / f"{t}.parquet").stat().st_mtime_ns for t in TABLES)
    )


# Keyed by the files' mtimes: rehash (~1 MB) only after `make seed` rewrote them.
@lru_cache(maxsize=4)
def _dataset_version(dataset_dir: Path, _mtimes: tuple[int, ...]) -> str:
    h = hashlib.sha256()
    for t in TABLES:
        h.update((dataset_dir / f"{t}.parquet").read_bytes())
    return h.hexdigest()[:12]


MAX_RESULT_ROWS = 5_000  # shared cap: browser posts at most this many rows


def open_dataset(dataset_dir: Path) -> duckdb.DuckDBPyConnection:
    """In-memory DuckDB with one table per Parquet file, then locked down.

    We materialize tables (CREATE TABLE AS) instead of views because views re-read the
    Parquet on every query, and we want to *disable file access* after setup: no
    read_csv('/etc/passwd'), no extension installs. The dataset is ~40k rows, so loading
    it takes a few ms and a few MB.
    """
    con = duckdb.connect(":memory:")
    for name in TABLES:
        path = (dataset_dir / f"{name}.parquet").as_posix().replace("'", "''")
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM read_parquet('{path}')")
    con.execute("SET enable_external_access = false")
    con.execute("SET lock_configuration = true")  # SQL can't flip the setting back
    return con
