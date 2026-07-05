"""Per-ticker scoring pipeline: EDGAR → parse → stage1 → stage2.

This is the single-ticker unit that the full-universe scan fans out over.
It deliberately reuses the existing edgar / llm / scoring modules so the
fixture acceptance path and the universe scan run identical logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from windvane.edgar import EdgarClient, cache_filing, extract_items, parse_submissions
from windvane.edgar.discover import FilingMeta, latest_pair
from windvane.llm import (
    FilingItems,
    Stage1Output,
    Stage2Output,
    critique_pivot_analysis,
    extract_pivot_signal,
)
from windvane.universe import Ticker


@dataclass(frozen=True)
class FilingPair:
    """Current + prior-year filing items, ready for the LLM diff."""

    current: FilingItems
    prior: FilingItems


@dataclass(frozen=True)
class ScanResult:
    """One ticker's full scoring outcome (pre-persistence)."""

    symbol: str
    name: str
    sector: str
    raw_strength: float
    raw_strength_critiqued: float
    narrative_summary: str
    current_accession: str
    prior_accession: str
    stage1: Stage1Output
    stage2: Stage2Output
    usage: dict[str, Any]


def _period_label(meta: FilingMeta) -> str:
    year = (meta.period_of_report or meta.filing_date).year
    return f"FY{year}" if meta.form == "10-K" else f"{meta.form} {meta.filing_date}"


def _to_items(cache_dir: Path, cik: str, client: EdgarClient, meta: FilingMeta) -> FilingItems:
    path = cache_filing(client, cache_dir, cik, meta)
    extracted = extract_items(path.read_text(encoding="utf-8"))
    return FilingItems(
        accession_no=meta.accession_no,
        period_label=_period_label(meta),
        item_1=extracted["item_1"],
        item_1a=extracted["item_1a"],
        item_7=extracted["item_7"],
    )


def prepare_filings(
    client: EdgarClient,
    ticker: Ticker,
    cache_dir: Path,
    *,
    form: str = "10-K",
) -> FilingPair | None:
    """Download + parse the current and prior-year filing for `ticker`.

    Returns None when the year-over-year diff is impossible (no prior filing)
    or when both parsed filings are empty (parser failure — e.g. an unusual
    layout). The caller treats None as "not scannable".
    """
    sub = client.get_submissions(ticker.cik)
    filings = parse_submissions(sub)
    same_form = [f for f in filings if f.form == form]
    if len(same_form) < 2:
        return None

    current_meta, prior_meta = latest_pair(filings, form)
    if prior_meta is None:
        return None

    current = _to_items(cache_dir, ticker.cik, client, current_meta)
    prior = _to_items(cache_dir, ticker.cik, client, prior_meta)

    # Guard against total parser failure: if neither filing yielded any of the
    # three items, the LLM has nothing to diff.
    if not any([current.item_1, current.item_1a, current.item_7]):
        return None
    if not any([prior.item_1, prior.item_1a, prior.item_7]):
        return None

    return FilingPair(current=current, prior=prior)


def score_ticker(
    *,
    llm_client: Any,
    edgar_client: EdgarClient,
    ticker: Ticker,
    cache_dir: Path,
    model: str | None = None,
    run_critique: bool = True,
) -> ScanResult | None:
    """Run the full pipeline for one ticker. Returns None if not scannable.

    When run_critique=False, stage 2 is skipped and raw_strength_critiqued
    falls back to the stage-1 raw_strength (cheap "stage-1-only" tier).
    """
    pair = prepare_filings(edgar_client, ticker, cache_dir)
    if pair is None:
        return None

    extra = {"model": model} if model else {}
    stage1, raw1 = extract_pivot_signal(
        llm_client,
        company_name=ticker.name,
        current=pair.current,
        prior=pair.prior,
        **extra,
    )

    if run_critique:
        stage2, raw2 = critique_pivot_analysis(
            llm_client,
            company_name=ticker.name,
            current=pair.current,
            prior=pair.prior,
            stage1=stage1,
            **extra,
        )
        critiqued = stage2["raw_strength_critiqued"]
    else:
        stage2 = {
            "evidence_review": [],
            "keyword_review": [],
            "raw_strength_adjustment": 0.0,
            "raw_strength_critiqued": stage1["raw_strength"],
            "critique_summary": "(stage-2 critique skipped)",
        }
        raw2 = {}
        critiqued = stage1["raw_strength"]

    return ScanResult(
        symbol=ticker.symbol,
        name=ticker.name,
        sector=ticker.sector,
        raw_strength=stage1["raw_strength"],
        raw_strength_critiqued=critiqued,
        narrative_summary=stage1.get("narrative_summary", ""),
        current_accession=pair.current.accession_no,
        prior_accession=pair.prior.accession_no,
        stage1=stage1,
        stage2=stage2,  # type: ignore[arg-type]
        usage={"stage1": raw1, "stage2": raw2},
    )
