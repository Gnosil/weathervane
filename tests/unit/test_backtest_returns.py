"""Trading-day offset + α math (no network)."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from windvane.backtest.prices import (
    default_end_date,
    entry_close,
    trading_day_offset,
)


def _series_from(prices: list[tuple[str, float]]) -> pd.Series:
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d, _ in prices])
    vals = [p for _, p in prices]
    return pd.Series(vals, index=idx)


def test_entry_close_returns_first_trading_day_at_or_after() -> None:
    s = _series_from([("2024-04-01", 100.0), ("2024-04-02", 101.0)])
    result = entry_close(s, date(2024, 4, 1))
    assert result is not None
    _, p = result
    assert p == 100.0


def test_entry_close_skips_weekend() -> None:
    # Friday 2024-03-29, Monday 2024-04-01
    s = _series_from([("2024-03-29", 99.0), ("2024-04-01", 100.0)])
    # Entry on Saturday 2024-03-30 should snap to Monday
    result = entry_close(s, date(2024, 3, 30))
    assert result is not None
    _, p = result
    assert p == 100.0


def test_trading_day_offset() -> None:
    s = _series_from(
        [(f"2024-04-{i:02d}", 100.0 + i) for i in range(1, 11)]  # 10 trading days
    )
    result = trading_day_offset(s, date(2024, 4, 1), 5)
    assert result is not None
    _, p = result
    # Entry row idx=0, +5 → idx=5 → 100 + 6 = 106
    assert p == 106.0


def test_trading_day_offset_beyond_series_returns_none() -> None:
    s = _series_from([("2024-04-01", 100.0), ("2024-04-02", 101.0)])
    result = trading_day_offset(s, date(2024, 4, 1), 60)
    assert result is None


def test_default_end_date_covers_120d_window() -> None:
    end = default_end_date(date(2024, 4, 1), max_window_days=120)
    # 120 * 1.45 + 30 ≈ 204 calendar days
    assert (end - date(2024, 4, 1)).days >= 174  # > 120 trading days worth


def test_entry_close_future_date_returns_none() -> None:
    s = _series_from([("2024-04-01", 100.0)])
    result = entry_close(s, date(2025, 1, 1))
    assert result is None


def test_pricecache_get_returns_none_on_miss(tmp_path) -> None:
    from windvane.backtest.prices import PriceCache

    cache = PriceCache(tmp_path / "cache")
    assert cache.get("DOCU", date(2024, 4, 1), date(2024, 8, 1)) is None


def test_pricecache_roundtrip(tmp_path) -> None:
    from windvane.backtest.prices import PriceCache

    cache = PriceCache(tmp_path / "cache")
    df = pd.DataFrame(
        {"Close": [100.0, 101.0]},
        index=pd.DatetimeIndex(["2024-04-01", "2024-04-02"]),
    )
    cache.put("DOCU", date(2024, 4, 1), date(2024, 8, 1), df)
    got = cache.get("DOCU", date(2024, 4, 1), date(2024, 8, 1))
    assert got is not None
    assert list(got["Close"]) == pytest.approx([100.0, 101.0])
