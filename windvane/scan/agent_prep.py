"""Prepare filing text for session-based (no-API-key) scoring.

The standalone `scan --all` path calls the Anthropic API directly and needs a
key. When the user has no key, we instead let the Claude Code session score
filings via sub-agents. Those sub-agents can't politely hammer EDGAR in
parallel (shared 10 req/s limit), so we do all downloading/parsing here in one
rate-limited pass, write a compact per-ticker text file, and emit a manifest
the scoring workflow consumes.

Item bodies are truncated to keep each ticker's prompt to ~20-25k tokens — the
pivot signal lives in segment structure, new risk categories, and the MD&A
opening, not in the full boilerplate tail.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from windvane.edgar import EdgarClient, extract_items, parse_submissions
from windvane.edgar.discover import latest_pair
from windvane.edgar.download import cache_filing
from windvane.universe import FIXTURES, Ticker, load_sp500_universe

# Per-item truncation caps (characters).
CAP_ITEM_1 = 30_000
CAP_ITEM_1A = 25_000
CAP_ITEM_7 = 35_000

POSITIVE_ANCHORS = ["DOCU", "TWLO", "HON", "SNAP", "NET"]


@dataclass(frozen=True)
class PrepRow:
    symbol: str
    name: str
    sector: str
    path: str
    current_accession: str
    prior_accession: str


def select_tickers(n: int, cache_path: Path) -> list[Ticker]:
    """Pick `n` tickers: known positive anchors first, then sector round-robin."""
    universe = load_sp500_universe(cache_path)
    by_symbol = {t.symbol: t for t in universe}

    chosen: dict[str, Ticker] = {}
    # 1. anchors (use universe row if present, else fixture row)
    fixtures_by_symbol = {t.symbol: t for t in FIXTURES}
    for sym in POSITIVE_ANCHORS:
        t = by_symbol.get(sym) or fixtures_by_symbol.get(sym)
        if t:
            chosen[sym] = t

    # 2. sector round-robin over the rest
    by_sector: dict[str, list[Ticker]] = {}
    for t in universe:
        if t.symbol in chosen:
            continue
        by_sector.setdefault(t.sector or "(unknown)", []).append(t)
    sectors = sorted(by_sector, key=lambda s: len(by_sector[s]), reverse=True)
    idx = 0
    while len(chosen) < n and any(by_sector.values()):
        sec = sectors[idx % len(sectors)]
        bucket = by_sector.get(sec)
        if bucket:
            t = bucket.pop(0)
            chosen[t.symbol] = t
        idx += 1

    return list(chosen.values())[:n]


def _truncate(text: str, cap: int) -> str:
    if len(text) <= cap:
        return text
    return text[:cap] + f"\n[... truncated {len(text) - cap} chars ...]"


def _render_prep_text(name: str, symbol: str, sector: str, current, prior) -> str:
    def block(label: str, items: dict) -> str:
        parts = [f"##### {label} #####"]
        parts.append("--- Item 1 Business ---")
        parts.append(_truncate(items["item_1"], CAP_ITEM_1) or "(empty)")
        parts.append("--- Item 1A Risk Factors ---")
        parts.append(_truncate(items["item_1a"], CAP_ITEM_1A) or "(empty)")
        parts.append("--- Item 7 MD&A ---")
        parts.append(_truncate(items["item_7"], CAP_ITEM_7) or "(empty)")
        return "\n\n".join(parts)

    header = f"=== COMPANY: {name} ({symbol}) | Sector: {sector} ==="
    return "\n\n".join([header, block("CURRENT FILING", current), block("PRIOR FILING", prior)])


def prepare(
    tickers: list[Ticker],
    *,
    user_agent: str,
    out_dir: Path,
    filings_cache: Path,
    progress=None,
) -> tuple[list[PrepRow], list[str]]:
    """Download+parse each ticker, write a compact prep file. Returns (rows, skipped)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[PrepRow] = []
    skipped: list[str] = []

    with EdgarClient(user_agent=user_agent) as client:
        for t in tickers:
            try:
                sub = client.get_submissions(t.cik)
                filings = parse_submissions(sub)
                same = [f for f in filings if f.form == "10-K"]
                if len(same) < 2:
                    skipped.append(f"{t.symbol} (no YoY 10-K)")
                    continue
                current_meta, prior_meta = latest_pair(filings, "10-K")
                if prior_meta is None:
                    skipped.append(f"{t.symbol} (no prior 10-K)")
                    continue

                cur_path = cache_filing(client, filings_cache, t.cik, current_meta)
                pri_path = cache_filing(client, filings_cache, t.cik, prior_meta)
                cur = extract_items(cur_path.read_text(encoding="utf-8"))
                pri = extract_items(pri_path.read_text(encoding="utf-8"))

                if not any([cur["item_1"], cur["item_1a"], cur["item_7"]]) or not any(
                    [pri["item_1"], pri["item_1a"], pri["item_7"]]
                ):
                    skipped.append(f"{t.symbol} (parse failed)")
                    continue

                text = _render_prep_text(t.name, t.symbol, t.sector, cur, pri)
                fpath = out_dir / f"{t.symbol}.txt"
                fpath.write_text(text, encoding="utf-8")
                rows.append(
                    PrepRow(
                        symbol=t.symbol,
                        name=t.name,
                        sector=t.sector,
                        path=str(fpath),
                        current_accession=current_meta.accession_no,
                        prior_accession=prior_meta.accession_no,
                    )
                )
                if progress is not None:
                    progress(t.symbol, True)
            except Exception as e:
                skipped.append(f"{t.symbol} ({type(e).__name__})")
                if progress is not None:
                    progress(t.symbol, False)

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps([asdict(r) for r in rows], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return rows, skipped
