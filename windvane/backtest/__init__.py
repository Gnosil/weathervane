"""Backtest harness — validate pool entries against real market performance."""

from windvane.backtest.prices import PriceCache, download_prices
from windvane.backtest.report import render_summary_markdown
from windvane.backtest.returns import BacktestPoint, compute_window_returns
from windvane.backtest.runner import (
    BacktestRow,
    backtest_fixtures,
    backtest_single,
    persist_results,
)

__all__ = [
    "BacktestPoint",
    "BacktestRow",
    "PriceCache",
    "backtest_fixtures",
    "backtest_single",
    "compute_window_returns",
    "download_prices",
    "persist_results",
    "render_summary_markdown",
]
