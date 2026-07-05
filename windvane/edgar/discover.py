"""Parse EDGAR submissions JSON into typed FilingMeta records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class FilingMeta:
    accession_no: str
    form: str
    filing_date: date
    period_of_report: date | None
    primary_document: str


def _safe_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def parse_submissions(submissions_json: dict[str, Any]) -> list[FilingMeta]:
    """Parse the 'filings.recent' block from a submissions JSON payload.

    Note: EDGAR also exposes paginated older filings via filings.files[].name;
    v0.1 only consumes the rolling 'recent' window (~1000 most recent).
    """
    recent = submissions_json.get("filings", {}).get("recent", {})
    accs = recent.get("accessionNumber", []) or []
    forms = recent.get("form", []) or []
    dates = recent.get("filingDate", []) or []
    periods = recent.get("reportDate", []) or []
    docs = recent.get("primaryDocument", []) or []

    n = min(len(accs), len(forms), len(dates), len(docs))
    out: list[FilingMeta] = []
    for i in range(n):
        d = _safe_date(dates[i])
        if d is None:
            continue
        period = _safe_date(periods[i] if i < len(periods) else None)
        out.append(
            FilingMeta(
                accession_no=accs[i],
                form=forms[i],
                filing_date=d,
                period_of_report=period,
                primary_document=docs[i],
            )
        )
    return out


def filter_filings(
    filings: list[FilingMeta],
    forms: set[str],
    since: date | None = None,
) -> list[FilingMeta]:
    """Filter by form type & filing-date floor. Preserves order."""
    out = []
    for f in filings:
        if f.form not in forms:
            continue
        if since and f.filing_date < since:
            continue
        out.append(f)
    return out


def latest_pair(filings: list[FilingMeta], form: str) -> tuple[FilingMeta, FilingMeta | None]:
    """Return (most_recent, prior_year_same_form) for a given form type.

    Used to feed (current, prior) into the LLM diff. Returns (most_recent, None)
    if no prior filing exists.
    """
    same = [f for f in filings if f.form == form]
    if not same:
        raise ValueError(f"No filings of form {form!r} in this list")
    # filings come newest-first from EDGAR; sort defensively
    same.sort(key=lambda f: f.filing_date, reverse=True)
    most_recent = same[0]
    prior = same[1] if len(same) > 1 else None
    return most_recent, prior
