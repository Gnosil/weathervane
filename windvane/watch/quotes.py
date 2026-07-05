"""Quote provider for the watch layer (yfinance, free, ~15-min delayed)."""

from __future__ import annotations

from dataclasses import dataclass

import yfinance as yf


@dataclass(frozen=True)
class Quote:
    symbol: str
    last: float
    prev_close: float
    change_pct: float
    volume: float
    avg_volume_20d: float
    vol_ratio: float
    high_20d: float
    low_20d: float
    at_20d_high: bool
    at_20d_low: bool


def fetch_quote(symbol: str) -> Quote | None:
    try:
        tk = yf.Ticker(symbol)
        hist = tk.history(period="2mo", interval="1d")
        if hist is None or hist.empty or len(hist) < 5:
            return None
        closes = hist["Close"].dropna()
        vols = hist["Volume"].dropna()
        prev_close = float(closes.iloc[-2])
        last = prev_close
        try:
            lp = getattr(tk.fast_info, "last_price", None)
            if lp:
                last = float(lp)
        except Exception:
            last = float(closes.iloc[-1])
        window = closes.iloc[-21:-1] if len(closes) > 21 else closes.iloc[:-1]
        high_20d = float(window.max())
        low_20d = float(window.min())
        avg_vol = float(vols.iloc[-21:-1].mean()) if len(vols) > 21 else float(vols.mean())
        today_vol = float(vols.iloc[-1])
        vol_ratio = (today_vol / avg_vol) if avg_vol > 0 else 0.0
        change_pct = (last / prev_close - 1.0) if prev_close > 0 else 0.0
        return Quote(symbol=symbol, last=last, prev_close=prev_close, change_pct=change_pct,
                     volume=today_vol, avg_volume_20d=avg_vol, vol_ratio=vol_ratio,
                     high_20d=high_20d, low_20d=low_20d,
                     at_20d_high=last >= high_20d, at_20d_low=last <= low_20d)
    except Exception:
        return None
