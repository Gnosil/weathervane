"""High-level backtest runner: single ticker, fixtures suite, all-pool."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from windvane.backtest.prices import PriceCache
from windvane.backtest.returns import BacktestPoint, compute_window_returns
from windvane.db import connect
from windvane.universe import FIXTURES

# Hardcoded entry dates for the v0.1 fixture suite.
# These approximate the SEC filing dates where the pivot signal would have
# been detected. v0.2 will derive these dynamically from the EDGAR cache.
FIXTURE_ENTRY_DATES: dict[str, date] = {
    # Positive samples
    "DOCU": date(2024, 3, 28),  # FY2024 10-K (IAM platform launch year)
    "TWLO": date(2024, 2, 14),  # FY2023 10-K (Segment operational review)
    "HON": date(2025, 2, 6),  # Three-way split announcement
    "SNAP": date(2025, 6, 10),  # AR Specs 2026 announcement
    "NET": date(2024, 2, 8),  # FY2023 10-K (Workers AI ramp)
    # Shell-pivot samples
    "BIRD": date(2026, 1, 15),  # NewBird AI rebrand window
    "CAPS": date(2025, 11, 1),  # Full Stack AI transition announcement
    # Negative samples (baseline date)
    "KO": date(2024, 4, 1),
    "PG": date(2024, 4, 1),
    "JNJ": date(2024, 4, 1),
    "WMT": date(2024, 4, 1),
    "JPM": date(2024, 4, 1),
}


@dataclass(frozen=True)
class BacktestRow:
    """Persisted backtest row, suitable for SQLite insertion or report rendering."""

    point: BacktestPoint
    entry_z: float | None
    entry_direction: str  # "long" | "short"
    fixture_role: str | None


def backtest_single(
    symbol: str,
    entry_date: date,
    *,
    direction: str = "long",
    entry_z: float | None = None,
    fixture_role: str | None = None,
    benchmark: str = "SPY",
    cache_dir: Path | None = None,
) -> BacktestRow:
    cache = PriceCache(cache_dir) if cache_dir else None
    point = compute_window_returns(symbol, entry_date, benchmark=benchmark, cache=cache)
    return BacktestRow(
        point=point,
        entry_z=entry_z,
        entry_direction=direction,
        fixture_role=fixture_role,
    )


def backtest_fixtures(
    *,
    benchmark: str = "SPY",
    cache_dir: Path | None = None,
) -> list[BacktestRow]:
    """Run the v0.1 12-fixture suite."""
    rows: list[BacktestRow] = []
    for tk in FIXTURES:
        entry = FIXTURE_ENTRY_DATES.get(tk.symbol)
        if entry is None:
            continue
        try:
            row = backtest_single(
                tk.symbol,
                entry,
                direction="long",
                fixture_role=tk.fixture_role,
                benchmark=benchmark,
                cache_dir=cache_dir,
            )
        except Exception as e:
            # Record as a failed row rather than crashing the whole suite
            row = BacktestRow(
                point=BacktestPoint(
                    symbol=tk.symbol,
                    entry_date=entry,
                    entry_close=float("nan"),
                    benchmark=benchmark,
                    return_pct={5: None, 20: None, 60: None, 120: None},
                    alpha_pct={5: None, 20: None, 60: None, 120: None},
                ),
                entry_z=None,
                entry_direction="long",
                fixture_role=tk.fixture_role,
            )
            # Attach error info as metadata via attribute (not on the frozen point)
            object.__setattr__(row, "_error", str(e))
        rows.append(row)
    return rows


def persist_results(db_path: Path, rows: list[BacktestRow]) -> int:
    """Insert rows into backtest_results table. Returns count inserted."""
    n = 0
    with connect(db_path) as conn:
        for r in rows:
            conn.execute(
                """
                INSERT INTO backtest_results (
                    symbol, entry_date, entry_z, entry_direction,
                    return_5d, return_20d, return_60d, return_120d,
                    alpha_5d, alpha_20d, alpha_60d, alpha_120d,
                    benchmark
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    r.point.symbol,
                    r.point.entry_date.isoformat(),
                    r.entry_z,
                    r.entry_direction,
                    r.point.return_pct.get(5),
                    r.point.return_pct.get(20),
                    r.point.return_pct.get(60),
                    r.point.return_pct.get(120),
                    r.point.alpha_pct.get(5),
                    r.point.alpha_pct.get(20),
                    r.point.alpha_pct.get(60),
                    r.point.alpha_pct.get(120),
                    r.point.benchmark,
                ),
            )
            n += 1
    return n
