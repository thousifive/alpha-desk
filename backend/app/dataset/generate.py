"""Deterministic generator for the fictional Meridian Capital market dataset.

Writes Parquet files to data/meridian/. The browser (DuckDB-WASM) and the grader (native
DuckDB) both read these same files, so expected answers always match what the user queries.

Every company, ticker, trader and book name here is invented.

Teaching quirks baked in on purpose (exercises rely on them):
- a handful of (date, ticker) price rows are missing
- NVLT lists mid-period (first price 2024-03-15)
- HLVR has an unadjusted 2:1 split on 2024-06-10 (see corporate_actions)
"""

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import polars as pl

SEED = 42
START = date(2023, 1, 2)
END = date(2025, 12, 31)
BOOK = "MERIDIAN-LS-1"
LATE_LISTING = ("NVLT", date(2024, 3, 15))
SPLIT = ("HLVR", date(2024, 6, 10), 2.0)
N_MISSING_ROWS = 12


@dataclass(frozen=True)
class Company:
    ticker: str
    name: str
    sector: str
    industry: str
    mcap_bucket: str  # "large" | "mid" | "small"


# ruff format would explode this table to one field per line, so skip formatting it.
# fmt: off
COMPANIES: tuple[Company, ...] = (
    Company("HLVR", "Halvorsen Robotics", "Technology", "Automation", "large"),
    Company("QBTX", "Qubitrix Systems", "Technology", "Semiconductors", "large"),
    Company("NVLT", "Novalith Cloud", "Technology", "Software", "mid"),
    Company("PXLR", "Pixelridge Software", "Technology", "Software", "mid"),
    Company("CRDX", "Cordex Networks", "Technology", "Networking", "mid"),
    Company("SYNP", "Synaptiq Labs", "Technology", "Software", "small"),
    Company("AURX", "Aurex Therapeutics", "Healthcare", "Biotech", "mid"),
    Company("MDVA", "Medivale Health", "Healthcare", "Providers", "large"),
    Company("GNSL", "Genosil Biosciences", "Healthcare", "Biotech", "small"),
    Company("CRVN", "Carvanta Medical", "Healthcare", "Devices", "mid"),
    Company("PLSE", "Pulsewell Diagnostics", "Healthcare", "Devices", "small"),
    Company("THRM", "Thermagen Pharma", "Healthcare", "Pharma", "large"),
    Company("BRKS", "Brookstead Bancorp", "Financials", "Banks", "large"),
    Company("LDGR", "Ledgerline Payments", "Financials", "Payments", "mid"),
    Company("KSTL", "Kestrel Insurance", "Financials", "Insurance", "mid"),
    Company("ORVL", "Orvell Asset Group", "Financials", "Asset Mgmt", "small"),
    Company("TNDR", "Tenderfield Credit", "Financials", "Consumer Credit", "small"),
    Company("VLTA", "Valtara Energy", "Energy", "Oil & Gas", "large"),
    Company("SOLR", "Solarean Power", "Energy", "Renewables", "mid"),
    Company("PTRX", "Petrix Midstream", "Energy", "Pipelines", "mid"),
    Company("GLDW", "Goldwind Drilling", "Energy", "Oil Services", "small"),
    Company("HYDR", "Hydrion Fuels", "Energy", "Renewables", "small"),
    Company("BRWL", "Brightwell Foods", "Consumer", "Food", "large"),
    Company("LUMN", "Lumina Apparel", "Consumer", "Apparel", "mid"),
    Company("CSKY", "Casky Beverages", "Consumer", "Beverages", "mid"),
    Company("TRVO", "Travoro Hotels", "Consumer", "Leisure", "small"),
    Company("NSTR", "Nestora Home", "Consumer", "Retail", "mid"),
    Company("MRKT", "Marketvale Stores", "Consumer", "Retail", "large"),
    Company("FRGE", "Forgeline Industrial", "Industrials", "Machinery", "large"),
    Company("AXLE", "Axlewright Transport", "Industrials", "Logistics", "mid"),
    Company("STRC", "Structa Building", "Industrials", "Construction", "mid"),
    Company("AERV", "Aerovance Dynamics", "Industrials", "Aerospace", "large"),
    Company("RLWY", "Railwick Freight", "Industrials", "Logistics", "small"),
    Company("GRDN", "Gridline Utilities", "Utilities", "Electric", "large"),
    Company("AQUA", "Aquaverde Water", "Utilities", "Water", "mid"),
    Company("PWRS", "Powerstead Gas", "Utilities", "Gas", "mid"),
    Company("VOLT", "Voltaris Grid", "Utilities", "Electric", "small"),
    Company("ORMN", "Ormond Minerals", "Materials", "Mining", "large"),
    Company("CHMX", "Chemexa Polymers", "Materials", "Chemicals", "mid"),
    Company("STLW", "Steelwater Metals", "Materials", "Steel", "mid"),
    Company("TMBR", "Timberlake Packaging", "Materials", "Packaging", "small"),
    Company("LTHM", "Lithmore Resources", "Materials", "Mining", "small"),
    Company("CMNK", "Commonlink Telecom", "Communication", "Telecom", "large"),
    Company("STRM", "Streamwell Media", "Communication", "Media", "mid"),
    Company("ADVZ", "Advizio Interactive", "Communication", "Advertising", "mid"),
    Company("GMRX", "Gamerix Studios", "Communication", "Gaming", "small"),
    Company("PRPT", "Proptera Realty", "Real Estate", "REIT", "mid"),
    Company("URBN", "Urbanest Properties", "Real Estate", "REIT", "large"),
    Company("DTCN", "Datacentra Trust", "Real Estate", "Data Centers", "mid"),
    Company("LOGX", "Logixa Warehousing", "Real Estate", "Industrial REIT", "small"),
)
# fmt: on

TRADERS = ("A. Okonkwo", "J. Lindqvist", "R. Mehra", "S. Castellano")
_HOLIDAYS = {(1, 1), (7, 4), (12, 25)}  # simplified: weekends + three fixed holidays


def trading_days(start: date = START, end: date = END) -> list[date]:
    days: list[date] = []
    d = start
    while d <= end:
        if d.weekday() < 5 and (d.month, d.day) not in _HOLIDAYS:
            days.append(d)
        d += timedelta(days=1)
    return days


def build_tickers() -> pl.DataFrame:
    listed = {LATE_LISTING[0]: LATE_LISTING[1]}
    return pl.DataFrame(
        {
            "ticker": [c.ticker for c in COMPANIES],
            "name": [c.name for c in COMPANIES],
            "sector": [c.sector for c in COMPANIES],
            "industry": [c.industry for c in COMPANIES],
            "mcap_bucket": [c.mcap_bucket for c in COMPANIES],
            "listed_on": [listed.get(c.ticker, START) for c in COMPANIES],
        }
    )


def build_prices(rng: np.random.Generator, days: list[date]) -> tuple[pl.DataFrame, np.ndarray]:
    """Simulate OHLCV with a one-factor-plus-sector model.

    Daily log return = beta * market + sector shock + idiosyncratic noise. Correlated
    returns make sector exposure and beta questions meaningful. Returns (prices, betas).
    """
    n_days, n_tk = len(days), len(COMPANIES)
    sectors = sorted({c.sector for c in COMPANIES})
    sector_idx = np.array([sectors.index(c.sector) for c in COMPANIES])

    betas = rng.uniform(0.6, 1.6, n_tk)
    idio_vol = rng.uniform(0.008, 0.022, n_tk)
    drift = rng.normal(0.0003, 0.0004, n_tk)

    market = rng.normal(0.0003, 0.010, n_days)
    sector_shocks = rng.normal(0.0, 0.006, (n_days, len(sectors)))
    # Broadcasting: (n_days, 1) * (n_tk,) → (n_days, n_tk) without an explicit loop.
    log_ret = (
        market[:, None] * betas
        + sector_shocks[:, sector_idx]
        + rng.normal(0.0, 1.0, (n_days, n_tk)) * idio_vol
        + drift
    )
    start_px = rng.uniform(15, 400, n_tk)
    close = start_px * np.exp(np.cumsum(log_ret, axis=0))

    # Opens gap from the previous close; highs/lows extend beyond the open-close range.
    prev_close = np.vstack([start_px, close[:-1]])
    open_ = prev_close * np.exp(rng.normal(0, 0.004, (n_days, n_tk)))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.006, (n_days, n_tk))))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.006, (n_days, n_tk))))
    volume = rng.lognormal(13.5, 0.5, (n_days, n_tk)).astype(np.int64) + 1_000

    split_tk, split_day, ratio = SPLIT
    split_col = [c.ticker for c in COMPANIES].index(split_tk)
    split_row = days.index(split_day)
    for arr in (open_, high, low, close):
        arr[split_row:, split_col] /= ratio  # unadjusted: price halves overnight
    volume[split_row:, split_col] = (volume[split_row:, split_col] * ratio).astype(np.int64)

    # Long format: one row per (date, ticker). np.repeat/np.tile build the key columns
    # in the same row-major order that .ravel() flattens the 2-D arrays.
    df = pl.DataFrame(
        {
            "date": np.repeat(np.array(days, dtype="datetime64[D]"), n_tk),
            "ticker": np.tile([c.ticker for c in COMPANIES], n_days),
            "open": open_.ravel(),
            "high": high.ravel(),
            "low": low.ravel(),
            "close": close.ravel(),
            "volume": volume.ravel(),
        }
    ).with_columns(pl.col("date").cast(pl.Date), pl.col(["open", "high", "low", "close"]).round(2))

    late_tk, late_day = LATE_LISTING
    df = df.filter(~((pl.col("ticker") == late_tk) & (pl.col("date") < late_day)))

    # Drop a few random rows (never a ticker's first day) to simulate gaps in the feed.
    candidates = df.filter(pl.col("date") > late_day).select("date", "ticker")
    pick = rng.choice(candidates.height, N_MISSING_ROWS, replace=False)
    missing = candidates[pick.tolist()]
    # An anti join keeps left rows with no match on the right: "everything except these".
    df = df.join(missing, on=["date", "ticker"], how="anti").sort("date", "ticker")
    return df, betas


def build_factors(rng: np.random.Generator, betas: np.ndarray) -> pl.DataFrame:
    size_map = {"large": 1.0, "mid": 0.0, "small": -1.0}
    n = len(COMPANIES)
    return pl.DataFrame(
        {
            "ticker": [c.ticker for c in COMPANIES],
            "beta": np.round(betas, 3),
            "value": np.round(rng.normal(0, 1, n), 3),
            "momentum": np.round(rng.normal(0, 1, n), 3),
            "size": np.round([size_map[c.mcap_bucket] + rng.normal(0, 0.3) for c in COMPANIES], 3),
            "quality": np.round(rng.normal(0, 1, n), 3),
        }
    )


def build_trades_and_positions(
    rng: np.random.Generator, prices: pl.DataFrame, days: list[date]
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """A long/short book: initial build on day one, small rebalances roughly weekly,
    and a new long in the late-listed name shortly after it lists."""
    tickers = [
        c.ticker for c in COMPANIES if c.ticker not in (SPLIT[0], LATE_LISTING[0])
    ]  # keep the split name out so positions don't need split adjustment
    chosen = rng.choice(tickers, 25, replace=False).tolist()
    longs, shorts = chosen[:15], chosen[15:]

    px = {(d, t): c for d, t, c in prices.select("date", "ticker", "close").iter_rows()}

    def price_on(d: date, t: str) -> float | None:
        return px.get((d, t))

    trades: list[dict[str, object]] = []
    held: dict[str, int] = {}

    def trade(d: date, t: str, signed_qty: int) -> None:
        p = price_on(d, t)
        if p is None or signed_qty == 0:
            return  # no price that day (missing row) → desk skips the trade
        fill = round(p * (1 + rng.normal(0, 0.0015)), 2)
        trades.append(
            {
                "trade_id": len(trades) + 1,
                "trade_date": d,
                "book": BOOK,
                "ticker": t,
                "side": "BUY" if signed_qty > 0 else "SELL",
                "quantity": abs(signed_qty),
                "price": fill,
                "trader": TRADERS[int(rng.integers(len(TRADERS)))],
            }
        )
        held[t] = held.get(t, 0) + signed_qty

    day0 = days[0]
    for t in longs:
        trade(day0, t, int(round(2_000_000 / price_on(day0, t) / 10) * 10))  # type: ignore[operator]
    for t in shorts:
        trade(day0, t, -int(round(1_500_000 / price_on(day0, t) / 10) * 10))  # type: ignore[operator]

    late_tk, late_day = LATE_LISTING
    late_entry = next(d for d in days if d >= late_day + timedelta(days=5))
    for d in days[1:]:
        if d == late_entry:
            trade(d, late_tk, int(round(1_000_000 / price_on(d, late_tk) / 10) * 10))  # type: ignore[operator]
        if d.weekday() == 0:  # Monday rebalance: trim or add to two names
            for t in rng.choice(sorted(held), 2, replace=False).tolist():
                cur = held[t]
                change = int(round(cur * rng.uniform(-0.25, 0.25) / 10) * 10)
                trade(d, t, change)

    trades_df = pl.DataFrame(trades).with_columns(pl.col("trade_date").cast(pl.Date))

    # Positions = running sum of signed trade quantity per ticker, carried forward daily.
    signed = trades_df.select(
        pl.col("trade_date").alias("date"),
        "ticker",
        pl.when(pl.col("side") == "BUY")
        .then(pl.col("quantity"))
        .otherwise(-pl.col("quantity"))
        .alias("qty"),
    )
    calendar = pl.DataFrame({"date": days}).with_columns(pl.col("date").cast(pl.Date))
    grid = calendar.join(signed.select("ticker").unique(), how="cross")
    positions = (
        grid.join(
            signed.group_by("date", "ticker").agg(pl.col("qty").sum()),
            on=["date", "ticker"],
            how="left",
        )
        .with_columns(pl.col("qty").fill_null(0))
        .sort("ticker", "date")
        # cum_sum().over("ticker") is a window function: a running total per ticker partition.
        .with_columns(pl.col("qty").cum_sum().over("ticker").alias("quantity"))
        .filter(pl.col("quantity") != 0)
        .select("date", pl.lit(BOOK).alias("book"), "ticker", "quantity")
        .sort("date", "ticker")
    )
    return trades_df, positions


def build_corporate_actions() -> pl.DataFrame:
    tk, d, ratio = SPLIT
    return pl.DataFrame({"ticker": [tk], "action_date": [d], "action": ["split"], "ratio": [ratio]})


def validate_ohlcv(df: pl.DataFrame) -> None:
    """Raise ValueError if the price table breaks basic OHLCV invariants.

    TODO(me): implement with Polars expressions (no Python loops over rows):
      - high >= max(open, close) and low <= min(open, close)
      - volume > 0
      - no duplicate (date, ticker) pairs
    The error message should name which check failed and how many rows broke it.
    Teaches: Polars expressions (pl.max_horizontal, filter, is_duplicated) and data validation.
    """
    raise NotImplementedError("TODO(me): validate_ohlcv")


def generate(out_dir: Path, *, validate: bool = False) -> dict[str, int]:
    """Build every table and write Parquet. Returns {table: row_count}."""
    rng = np.random.default_rng(SEED)  # one seeded RNG → byte-for-byte reproducible output
    days = trading_days()
    tickers = build_tickers()
    prices, betas = build_prices(rng, days)
    if validate:
        validate_ohlcv(prices)
    factors = build_factors(rng, betas)
    trades, positions = build_trades_and_positions(rng, prices, days)

    tables = {
        "tickers": tickers,
        "prices": prices,
        "factors": factors,
        "trades": trades,
        "positions": positions,
        "corporate_actions": build_corporate_actions(),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.write_parquet(out_dir / f"{name}.parquet")
    return {name: df.height for name, df in tables.items()}
