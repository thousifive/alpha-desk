from pathlib import Path

import duckdb
import polars as pl
import pytest

from app.dataset.generate import LATE_LISTING, N_MISSING_ROWS, SPLIT, generate, trading_days


@pytest.fixture(scope="module")
def dataset_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("meridian")
    generate(out)
    return out


def _con(d: Path) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    for f in d.glob("*.parquet"):
        con.execute(f"CREATE VIEW {f.stem} AS SELECT * FROM read_parquet('{f}')")
    return con


def test_writes_all_tables(dataset_dir: Path) -> None:
    names = {p.stem for p in dataset_dir.glob("*.parquet")}
    assert names == {"tickers", "prices", "factors", "trades", "positions", "corporate_actions"}


def test_generation_is_deterministic(dataset_dir: Path, tmp_path: Path) -> None:
    generate(tmp_path)
    for f in dataset_dir.glob("*.parquet"):
        assert pl.read_parquet(f).equals(pl.read_parquet(tmp_path / f.name)), f.name


def test_price_row_count_reflects_quirks(dataset_dir: Path) -> None:
    con = _con(dataset_dir)
    n_days = len(trading_days())
    late_days = sum(1 for d in trading_days() if d < LATE_LISTING[1])
    expected = 50 * n_days - late_days - N_MISSING_ROWS
    assert con.sql("SELECT count(*) FROM prices").fetchone() == (expected,)


def test_ohlc_invariants_hold(dataset_dir: Path) -> None:
    bad = _con(dataset_dir).sql(
        "SELECT count(*) FROM prices "
        "WHERE high < greatest(open, close) OR low > least(open, close) OR volume <= 0"
    )
    assert bad.fetchone() == (0,)


def test_late_listing_and_split(dataset_dir: Path) -> None:
    con = _con(dataset_dir)
    tk, listed = LATE_LISTING
    assert con.sql(f"SELECT min(date) FROM prices WHERE ticker = '{tk}'").fetchone() == (listed,)
    split_tk, split_day, ratio = SPLIT
    row = con.sql(
        f"""SELECT last(close ORDER BY date) FILTER (WHERE date < '{split_day}') /
                   first(close ORDER BY date) FILTER (WHERE date >= '{split_day}')
            FROM prices WHERE ticker = '{split_tk}'"""
    ).fetchone()
    assert row is not None
    assert row[0] == pytest.approx(ratio, rel=0.15)  # one day of noise on top of the split


def test_positions_match_cumulative_trades(dataset_dir: Path) -> None:
    con = _con(dataset_dir)
    mismatches = con.sql(
        """WITH t AS (
             SELECT ticker, sum(CASE side WHEN 'BUY' THEN quantity ELSE -quantity END) AS net
             FROM trades GROUP BY ticker),
           last_pos AS (
             SELECT ticker, quantity FROM positions
             WHERE date = (SELECT max(date) FROM positions))
           SELECT count(*) FROM t LEFT JOIN last_pos USING (ticker)
           WHERE coalesce(last_pos.quantity, 0) <> t.net"""
    )
    assert mismatches.fetchone() == (0,)


def test_book_is_long_short(dataset_dir: Path) -> None:
    longs, shorts = _con(dataset_dir).sql(
        "SELECT count(*) FILTER (WHERE quantity > 0), count(*) FILTER (WHERE quantity < 0) "
        "FROM positions WHERE date = (SELECT min(date) FROM positions)"
    ).fetchone() or (0, 0)
    assert longs > 0 and shorts > 0
