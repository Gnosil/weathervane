"""T+N return + alpha (excess return vs SPY) computation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from windvane.backtest.prices import (
    PriceCache,
    default_end_date,
    download_prices,
    entry_close,
    trading_day_offset,
)

DEFAULT_WINDOWS = (5, 20, 60, 120)


@dataclass(frozen=True)
class BacktestPoint:
    """One (entry, ticker) backtest result."""

    symbol: str
    entry_date: date
    entry_close: float
    benchmark: str
    return_pct: dict[int, float | None]  # window_days -> return % (e.g. 0.123 = +12.3%)
    alpha_pct: dict[int, float | None]  # window_days -> alpha vs benchmark


def _close_series(df: pd.DataFrame) -> pd.Series:
    if "Close" not in df.columns:
        raise RuntimeError("Price frame missing 'Close' column")
    return df["Close"].dropna()


def compute_window_returns(
    symbol: str,
    entry_date: date,
    *,
    benchmark: str = "SPY",
    windows: tuple[int, ...] = DEFAULT_WINDOWS,
    cache: PriceCache | None = None,
) -> BacktestPoint:
    """Compute T+N return + alpha for `symbol` from `entry_date`."""
    end = default_end_date(entry_date, max_window_days=max(windows))
    ticker_df = download_prices(symbol, entry_date, end, cache=cache)
    bench_df = download_prices(benchmark, entry_date, end, cache=cache)

    tk_close = _close_series(ticker_df)
    bench_close = _close_series(bench_df)

    tk_entry = entry_close(tk_close, entry_date)
    bench_entry = entry_close(bench_close, entry_date)
    if tk_entry is None or bench_entry is None:
        raise RuntimeError(
            f"No trading-day price for {symbol}/{benchmark} on or after {entry_date}"
        )
    _, tk_p0 = tk_entry
    _, bench_p0 = bench_entry

    returns: dict[int, float | None] = {}
    alphas: dict[int, float | None] = {}
    for n in windows:
        tk_pt = trading_day_offset(tk_close, entry_date, n)
        bench_pt = trading_day_offset(bench_close, entry_date, n)
        if tk_pt is None or bench_pt is None:
            returns[n] = None
            alphas[n] = None
            continue
        _, tk_pn = tk_pt
        _, bench_pn = bench_pt
        r_tk = tk_pn / tk_p0 - 1.0
        r_bench = bench_pn / bench_p0 - 1.0
        returns[n] = r_tk
        alphas[n] = r_tk - r_bench

    return BacktestPoint(
        symbol=symbol,
        entry_date=entry_date,
        entry_close=tk_p0,
        benchmark=benchmark,
        return_pct=returns,
        alpha_pct=alphas,
    )
