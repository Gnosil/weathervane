"""Anomaly rules for the watch layer (simple, explainable, no LLM)."""

from __future__ import annotations

from dataclasses import dataclass

from windvane.watch.quotes import Quote

MOVE_PCT = 0.05
VOL_RATIO = 2.0


@dataclass(frozen=True)
class Alert:
    symbol: str
    kind: str
    message: str
    severity: str


def evaluate(q: Quote) -> list[Alert]:
    alerts: list[Alert] = []
    pct = q.change_pct * 100
    if q.change_pct >= MOVE_PCT:
        alerts.append(Alert(q.symbol, "surge", f"{q.symbol} 大涨 {pct:+.1f}% (现价 {q.last:.2f})", "high"))
    elif q.change_pct <= -MOVE_PCT:
        alerts.append(Alert(q.symbol, "drop", f"{q.symbol} 大跌 {pct:+.1f}% (现价 {q.last:.2f})", "high"))
    if q.at_20d_high and q.change_pct > 0:
        alerts.append(Alert(q.symbol, "breakout_high", f"{q.symbol} 突破 20 日新高 {q.last:.2f}", "medium"))
    elif q.at_20d_low and q.change_pct < 0:
        alerts.append(Alert(q.symbol, "breakdown_low", f"{q.symbol} 跌破 20 日新低 {q.last:.2f}", "medium"))
    if q.vol_ratio >= VOL_RATIO:
        alerts.append(Alert(q.symbol, "volume", f"{q.symbol} 放量 {q.vol_ratio:.1f}× (异常成交)", "medium"))
    return alerts
