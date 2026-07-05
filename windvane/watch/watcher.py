"""Watch loop: poll the watchlist, detect anomalies, notify."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from windvane.watch.notify import notify_macos
from windvane.watch.quotes import fetch_quote
from windvane.watch.rules import Alert, evaluate

ET = ZoneInfo("America/New_York")
@dataclass
class WatchConfig:
    symbols: list[str]
    interval_sec: int = 900
    offhours_sec: int = 3600
    notify: bool = True
    alerts_log: Path | None = None
def load_watchlist(reports_dir: Path, *, top: int = 15) -> list[str]:
    scan_dir = reports_dir / "scan"
    if not scan_dir.exists():
        return []
    for d in sorted([x for x in scan_dir.iterdir() if x.is_dir()], reverse=True):
        rj = d / "results.json"
        if rj.exists():
            rows = json.loads(rj.read_text(encoding="utf-8"))
            seen, out = set(), []
            for r in rows[:top]:
                s = r.get("symbol")
                if s and s not in seen:
                    seen.add(s)
                    out.append(s)
            return out
    return []
def is_market_hours(now_et: datetime) -> bool:
    if now_et.weekday() >= 5:
        return False
    m = now_et.hour * 60 + now_et.minute
    return 570 <= m <= 960
def run_once(symbols, *, notify, seen, log) -> list[Alert]:
    fired = []
    for sym in symbols:
        q = fetch_quote(sym)
        if q is None:
            continue
        for a in evaluate(q):
            key = f"{a.symbol}:{a.kind}"
            if key in seen:
                continue
            seen.add(key)
            fired.append(a)
            if notify:
                notify_macos("风向标 · 异动提醒", a.message, subtitle=a.symbol)
            if log:
                log(a)
    return fired
def watch_loop(cfg: WatchConfig, *, once: bool = False, clock=None) -> list[Alert]:
    now = clock or (lambda: datetime.now(ET))
    seen, all_fired, lp = set(), [], cfg.alerts_log
    def log(a):
        if lp is None:
            return
        lp.parent.mkdir(parents=True, exist_ok=True)
        with lp.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": now().isoformat(), "symbol": a.symbol, "kind": a.kind, "message": a.message}, ensure_ascii=False) + "\n")
    while True:
        rth = is_market_hours(now())
        if rth:
            all_fired.extend(run_once(cfg.symbols, notify=cfg.notify, seen=seen, log=log))
        if once:
            if not rth:
                all_fired.extend(run_once(cfg.symbols, notify=cfg.notify, seen=seen, log=log))
            return all_fired
        time.sleep(cfg.interval_sec if rth else cfg.offhours_sec)
