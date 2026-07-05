"""Dry-run planner: probe coverage + estimate cost BEFORE spending on LLM.

Two free, no-key passes:
1. coverage probe — pull each ticker's submissions JSON, check whether a
   year-over-year 10-K diff is even possible (current + prior present).
2. token sample — download + parse a small sample of filings, measure real
   Item 1/1A/7 size, and extrapolate cost across the scannable set.

This produces the honest artifact the user needs to choose a spend tier.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from windvane.edgar import EdgarClient, extract_items, parse_submissions
from windvane.edgar.discover import latest_pair
from windvane.edgar.download import cache_filing
from windvane.universe import Ticker

# Claude Sonnet 4.5 pricing (USD per 1M tokens), as of 2026-05.
PRICE_INPUT = 3.00
PRICE_OUTPUT = 15.00
PRICE_CACHE_WRITE = 3.75
PRICE_CACHE_READ = 0.30
BATCH_DISCOUNT = 0.50  # Message Batches API: 50% off

# Per-call output budgets (incl. extended thinking), tokens.
STAGE1_OUTPUT_TOKENS = 6000
STAGE2_OUTPUT_TOKENS = 4000
# Stage-2 fresh input on top of the cached prior filing: current items already
# in context via cache, plus the stage-1 JSON (~3k).
STAGE2_FRESH_INPUT_TOKENS = 15000

CHARS_PER_TOKEN = 4  # rough heuristic for English filing prose


@dataclass(frozen=True)
class PlanRow:
    symbol: str
    cik: str
    name: str
    sector: str
    has_current: bool
    has_prior: bool
    scannable: bool
    note: str


@dataclass
class ScanPlan:
    rows: list[PlanRow] = field(default_factory=list)

    @property
    def scannable(self) -> list[PlanRow]:
        return [r for r in self.rows if r.scannable]

    def coverage_by_sector(self) -> dict[str, tuple[int, int]]:
        """sector -> (scannable, total)."""
        out: dict[str, list[int]] = {}
        for r in self.rows:
            agg = out.setdefault(r.sector or "(unknown)", [0, 0])
            agg[1] += 1
            if r.scannable:
                agg[0] += 1
        return {k: (v[0], v[1]) for k, v in out.items()}


def build_plan(
    client: EdgarClient,
    tickers: list[Ticker],
    *,
    form: str = "10-K",
    progress=None,
) -> ScanPlan:
    """Probe each ticker's submissions to determine YoY-diff feasibility."""
    plan = ScanPlan()
    for t in tickers:
        has_current = has_prior = False
        note = ""
        try:
            sub = client.get_submissions(t.cik)
            filings = parse_submissions(sub)
            same = [f for f in filings if f.form == form]
            has_current = len(same) >= 1
            has_prior = len(same) >= 2
            if not has_current:
                note = f"no {form}"
            elif not has_prior:
                note = f"only one {form} (no prior year)"
        except Exception as e:
            note = f"error: {type(e).__name__}"
        plan.rows.append(
            PlanRow(
                symbol=t.symbol,
                cik=t.cik,
                name=t.name,
                sector=t.sector,
                has_current=has_current,
                has_prior=has_prior,
                scannable=has_prior,
                note=note,
            )
        )
        if progress is not None:
            progress(t.symbol)
    return plan


@dataclass(frozen=True)
class TokenSample:
    n_sampled: int
    median_pair_input_tokens: int
    mean_pair_input_tokens: int
    samples: list[tuple[str, int]]  # (symbol, pair_input_tokens)


def sample_filing_tokens(
    client: EdgarClient,
    tickers: list[Ticker],
    cache_dir: Path,
    *,
    n: int = 8,
    form: str = "10-K",
    progress=None,
) -> TokenSample:
    """Download+parse a sample; measure real (current+prior) input token size."""
    sizes: list[tuple[str, int]] = []
    for t in tickers:
        if len(sizes) >= n:
            break
        try:
            sub = client.get_submissions(t.cik)
            filings = parse_submissions(sub)
            same = [f for f in filings if f.form == form]
            if len(same) < 2:
                continue
            current_meta, prior_meta = latest_pair(filings, form)
            if prior_meta is None:
                continue
            total_chars = 0
            for meta in (current_meta, prior_meta):
                path = cache_filing(client, cache_dir, t.cik, meta)
                items = extract_items(path.read_text(encoding="utf-8"))
                total_chars += len(items["item_1"]) + len(items["item_1a"]) + len(items["item_7"])
            sizes.append((t.symbol, total_chars // CHARS_PER_TOKEN))
            if progress is not None:
                progress(t.symbol)
        except Exception:
            continue

    if not sizes:
        return TokenSample(0, 0, 0, [])
    vals = sorted(s for _, s in sizes)
    median = vals[len(vals) // 2]
    mean = sum(vals) // len(vals)
    return TokenSample(
        n_sampled=len(sizes),
        median_pair_input_tokens=median,
        mean_pair_input_tokens=mean,
        samples=sizes,
    )


@dataclass(frozen=True)
class CostEstimate:
    n_scannable: int
    pair_input_tokens: int
    per_ticker_sync_usd: float
    per_ticker_batch_usd: float
    total_sync_usd: float
    total_batch_usd: float
    stage1_only_total_sync_usd: float


def estimate_cost(n_scannable: int, pair_input_tokens: int) -> CostEstimate:
    """Estimate spend for the full two-stage scan over `n_scannable` tickers.

    Cost model per ticker (two-stage):
      Stage 1: write prior filing to cache + read current+prior as input,
               produce stage-1 output.
        - cache write (prior):        pair/2 tokens @ CACHE_WRITE
        - fresh input (current):      pair/2 tokens @ INPUT
        - output:                     STAGE1_OUTPUT @ OUTPUT
      Stage 2: prior re-read from cache, small fresh input, stage-2 output.
        - cache read (prior):         pair/2 tokens @ CACHE_READ
        - fresh input (current+json): STAGE2_FRESH_INPUT @ INPUT
        - output:                     STAGE2_OUTPUT @ OUTPUT
    """
    half = pair_input_tokens / 2.0
    m = 1_000_000.0

    s1 = (
        half * PRICE_CACHE_WRITE / m
        + half * PRICE_INPUT / m
        + STAGE1_OUTPUT_TOKENS * PRICE_OUTPUT / m
    )
    s2 = (
        half * PRICE_CACHE_READ / m
        + STAGE2_FRESH_INPUT_TOKENS * PRICE_INPUT / m
        + STAGE2_OUTPUT_TOKENS * PRICE_OUTPUT / m
    )
    per_sync = s1 + s2
    per_batch = per_sync * BATCH_DISCOUNT
    stage1_only_sync = s1

    return CostEstimate(
        n_scannable=n_scannable,
        pair_input_tokens=pair_input_tokens,
        per_ticker_sync_usd=per_sync,
        per_ticker_batch_usd=per_batch,
        total_sync_usd=per_sync * n_scannable,
        total_batch_usd=per_batch * n_scannable,
        stage1_only_total_sync_usd=stage1_only_sync * n_scannable,
    )
