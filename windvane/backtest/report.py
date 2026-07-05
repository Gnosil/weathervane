"""Markdown report rendering for backtest results."""

from __future__ import annotations

import statistics
from datetime import date

from windvane.backtest.runner import BacktestRow


def _fmt_pct(v: float | None) -> str:
    if v is None:
        return "N/A"
    return f"{v * 100:+.2f}%"


def _hit_rate(rows: list[BacktestRow], window: int) -> str:
    vals = [r.point.alpha_pct.get(window) for r in rows]
    nonnull = [v for v in vals if v is not None]
    if not nonnull:
        return "N/A"
    hits = sum(1 for v in nonnull if v > 0)
    return f"{hits}/{len(nonnull)} ({100 * hits / len(nonnull):.0f}%)"


def _mean_alpha(rows: list[BacktestRow], window: int) -> str:
    vals = [
        r.point.alpha_pct.get(window) for r in rows if r.point.alpha_pct.get(window) is not None
    ]
    if not vals:
        return "N/A"
    return f"{statistics.mean(vals) * 100:+.2f}%"


def render_summary_markdown(
    rows: list[BacktestRow],
    *,
    title: str = "Windvane Backtest",
    generated_on: date | None = None,
) -> str:
    """Render a per-row table + group summaries + acceptance check."""
    generated_on = generated_on or date.today()

    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"_Generated: {generated_on.isoformat()}_  ")
    lines.append("_Benchmark: SPY  ·  Windows: T+5 / T+20 / T+60 / T+120 trading days_")
    lines.append("")
    lines.append("> 本系统输出基于公开信息的算法分析, 不构成任何投资建议或财务建议。")
    lines.append("")

    # Per-row table
    lines.append("## Per-fixture results")
    lines.append("")
    lines.append("| Symbol | Role | Entry | T+5 α | T+20 α | T+60 α | T+120 α |")
    lines.append("|---|---|---|---:|---:|---:|---:|")
    for r in rows:
        lines.append(
            f"| {r.point.symbol} "
            f"| {r.fixture_role or '-'} "
            f"| {r.point.entry_date.isoformat()} "
            f"| {_fmt_pct(r.point.alpha_pct.get(5))} "
            f"| {_fmt_pct(r.point.alpha_pct.get(20))} "
            f"| {_fmt_pct(r.point.alpha_pct.get(60))} "
            f"| {_fmt_pct(r.point.alpha_pct.get(120))} |"
        )
    lines.append("")

    # Group summaries
    by_role: dict[str, list[BacktestRow]] = {}
    for r in rows:
        by_role.setdefault(r.fixture_role or "(none)", []).append(r)

    lines.append("## Summary by fixture role")
    lines.append("")
    lines.append("| Role | n | Hit rate (T+60) | Mean α (T+60) | Mean α (T+120) |")
    lines.append("|---|---:|---:|---:|---:|")
    for role in ("positive", "shell", "negative", "(none)"):
        if role not in by_role:
            continue
        group = by_role[role]
        lines.append(
            f"| {role} | {len(group)} | "
            f"{_hit_rate(group, 60)} | "
            f"{_mean_alpha(group, 60)} | "
            f"{_mean_alpha(group, 120)} |"
        )
    lines.append("")

    # v0.1 acceptance check (spec §9.5)
    lines.append("## v0.1 Acceptance check")
    lines.append("")
    pos = by_role.get("positive", [])
    pos_mean60 = _mean_alpha(pos, 60)
    neg = by_role.get("negative", [])
    neg_mean60 = _mean_alpha(neg, 60)
    lines.append(f"- Positive samples (n={len(pos)}): mean α_60d = {pos_mean60} (target: > 0)")
    lines.append(
        f"- Negative samples (n={len(neg)}): mean α_60d = {neg_mean60} (target: |α_60d| < 5% per fixture)"
    )
    shell = by_role.get("shell", [])
    lines.append(
        f"- Shell samples (n={len(shell)}): direction depends on quality grade — "
        f"will be wired to verification module in v0.2."
    )

    return "\n".join(lines) + "\n"
