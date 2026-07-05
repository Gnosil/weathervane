"""Backtest report rendering (no network)."""

from __future__ import annotations

from datetime import date

from windvane.backtest.report import render_summary_markdown
from windvane.backtest.returns import BacktestPoint
from windvane.backtest.runner import BacktestRow


def _row(
    symbol: str,
    role: str,
    *,
    alpha_60: float | None = 0.05,
    alpha_120: float | None = 0.10,
) -> BacktestRow:
    return BacktestRow(
        point=BacktestPoint(
            symbol=symbol,
            entry_date=date(2024, 4, 1),
            entry_close=100.0,
            benchmark="SPY",
            return_pct={5: 0.01, 20: 0.02, 60: alpha_60 or 0, 120: alpha_120 or 0},
            alpha_pct={5: 0.01, 20: 0.02, 60: alpha_60, 120: alpha_120},
        ),
        entry_z=None,
        entry_direction="long",
        fixture_role=role,
    )


def test_renders_table_rows_for_each_fixture() -> None:
    rows = [_row("DOCU", "positive"), _row("KO", "negative", alpha_60=0.0, alpha_120=0.01)]
    md = render_summary_markdown(rows)
    assert "| DOCU |" in md
    assert "| KO |" in md


def test_includes_acceptance_section() -> None:
    rows = [_row("DOCU", "positive")]
    md = render_summary_markdown(rows)
    assert "Acceptance check" in md
    assert "Positive samples" in md


def test_handles_missing_alpha_as_NA() -> None:
    rows = [_row("BIRD", "shell", alpha_60=None, alpha_120=None)]
    md = render_summary_markdown(rows)
    assert "N/A" in md


def test_summary_groups_by_role() -> None:
    rows = [
        _row("DOCU", "positive", alpha_60=0.10, alpha_120=0.15),
        _row("TWLO", "positive", alpha_60=0.05, alpha_120=0.08),
        _row("KO", "negative", alpha_60=0.01, alpha_120=0.02),
    ]
    md = render_summary_markdown(rows)
    # Should show 2 positives in their own row, 1 negative in another
    assert "| positive | 2 |" in md
    assert "| negative | 1 |" in md
