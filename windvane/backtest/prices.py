"""yfinance wrapper with on-disk pickle cache.

Avoids hammering yfinance on repeated runs. Cache key = (symbol, start, end).
We use pickle rather than parquet to avoid an extra heavy dependency.
"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
import yfinance as yf

if TYPE_CHECKING:
    pass


def _cache_key(symbol: str, start: date, end: date) -> str:
    h = hashlib.sha1(f"{symbol}|{start.isoformat()}|{end.isoformat()}".encode()).hexdigest()
    return f"{symbol.upper()}-{h[:10]}"


class PriceCache:
    """Tiny pickle-backed cache for yfinance OHLC data."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def path(self, symbol: str, start: date, end: date) -> Path:
        return self.cache_dir / f"{_cache_key(symbol, start, end)}.pkl"

    def get(self, symbol: str, start: date, end: date) -> pd.DataFrame | None:
        p = self.path(symbol, start, end)
        if not p.exists():
            return None
        try:
            return pd.read_pickle(p)
        except Exception:
            return None

    def put(self, symbol: str, start: date, end: date, df: pd.DataFrame) -> None:
        df.to_pickle(self.path(symbol, start, end))


def download_prices(
    symbol: str,
    start: date,
    end: date,
    cache: PriceCache | None = None,
) -> pd.DataFrame:
    """Fetch daily OHLC from yfinance; cache to parquet.

    Returns a DataFrame with at least a 'Close' column indexed by trading-day
    DatetimeIndex (auto_adjust=True so 'Close' is split/dividend-adjusted).
    """
    if cache is not None:
        cached = cache.get(symbol, start, end)
        if cached is not None and not cached.empty:
            return cached

    df = yf.download(
        symbol,
        start=start.isoformat(),
        end=end.isoformat(),
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    if df is None or df.empty:
        raise RuntimeError(f"yfinance returned no data for {symbol} {start}..{end}")

    # yfinance may return multi-index columns when group_by='ticker'. Flatten.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    if cache is not None:
        cache.put(symbol, start, end, df)
    return df


def trading_day_offset(
    close_series: pd.Series, entry_date: date, n_days: int
) -> tuple[pd.Timestamp, float] | None:
    """Find the (date, close) at `n_days` trading days after entry.

    `entry_date` is mapped to the first trading day on or after it. The Nth
    trading day offset is then by row position in the close series. Returns
    None if the offset falls beyond the series.
    """
    entry_ts = pd.Timestamp(entry_date)
    idx = close_series.index.searchsorted(entry_ts)
    target_idx = idx + n_days
    if target_idx >= len(close_series):
        return None
    return close_series.index[target_idx], float(close_series.iloc[target_idx])


def entry_close(close_series: pd.Series, entry_date: date) -> tuple[pd.Timestamp, float] | None:
    """Close on the first trading day on or after entry_date."""
    entry_ts = pd.Timestamp(entry_date)
    idx = close_series.index.searchsorted(entry_ts)
    if idx >= len(close_series):
        return None
    return close_series.index[idx], float(close_series.iloc[idx])


def default_end_date(entry: date, max_window_days: int = 120) -> date:
    """End date for yfinance fetch: entry + enough calendar days to cover
    `max_window_days` of trading + a buffer for weekends/holidays."""
    # 120 trading days ≈ 168 calendar days; add 30-day buffer.
    return entry + timedelta(days=int(max_window_days * 1.45) + 30)
