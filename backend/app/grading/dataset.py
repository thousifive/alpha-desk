"""Load the Meridian Parquet files into DuckDB tables with the names the browser uses."""

from pathlib import Path

import duckdb

TABLES = ("tickers", "prices", "factors", "trades", "positions", "corporate_actions")
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
