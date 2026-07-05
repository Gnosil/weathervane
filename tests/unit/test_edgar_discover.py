"""Submissions JSON parser tests."""

from __future__ import annotations

from datetime import date

from windvane.edgar.discover import (
    FilingMeta,
    filter_filings,
    latest_pair,
    parse_submissions,
)


def _fake_submissions(rows: list[dict]) -> dict:
    """Build a submissions-JSON-shaped dict from per-row dicts."""
    keys = ["accessionNumber", "form", "filingDate", "reportDate", "primaryDocument"]
    cols = {k: [] for k in keys}
    for r in rows:
        for k in keys:
            cols[k].append(r.get(k, ""))
    return {"filings": {"recent": cols}}


def test_parse_basic() -> None:
    sub = _fake_submissions(
        [
            {
                "accessionNumber": "0001-25-001",
                "form": "10-K",
                "filingDate": "2025-03-15",
                "reportDate": "2024-12-31",
                "primaryDocument": "co-20241231.htm",
            },
            {
                "accessionNumber": "0001-24-002",
                "form": "10-K",
                "filingDate": "2024-03-12",
                "reportDate": "2023-12-31",
                "primaryDocument": "co-20231231.htm",
            },
            {
                "accessionNumber": "0001-25-003",
                "form": "8-K",
                "filingDate": "2025-05-01",
                "reportDate": "",
                "primaryDocument": "co-event.htm",
            },
        ]
    )
    filings = parse_submissions(sub)
    assert len(filings) == 3
    assert filings[0].form == "10-K"
    assert filings[0].filing_date == date(2025, 3, 15)
    assert filings[0].period_of_report == date(2024, 12, 31)
    assert filings[2].period_of_report is None


def test_parse_handles_empty_or_malformed_dates() -> None:
    sub = _fake_submissions(
        [
            {"accessionNumber": "x", "form": "10-K", "filingDate": "not-a-date"},
            {
                "accessionNumber": "y",
                "form": "10-Q",
                "filingDate": "2025-06-01",
                "primaryDocument": "y.htm",
            },
        ]
    )
    filings = parse_submissions(sub)
    assert len(filings) == 1
    assert filings[0].accession_no == "y"


def test_filter_filings_by_form_and_date() -> None:
    filings = [
        FilingMeta("a", "10-K", date(2025, 3, 1), None, "a.htm"),
        FilingMeta("b", "8-K", date(2025, 4, 1), None, "b.htm"),
        FilingMeta("c", "10-K", date(2023, 3, 1), None, "c.htm"),
    ]
    out = filter_filings(filings, {"10-K"}, since=date(2024, 1, 1))
    assert len(out) == 1
    assert out[0].accession_no == "a"


def test_latest_pair_returns_current_and_prior() -> None:
    filings = [
        FilingMeta("c25", "10-K", date(2025, 3, 1), None, "x.htm"),
        FilingMeta("c24", "10-K", date(2024, 3, 1), None, "y.htm"),
        FilingMeta("c23", "10-K", date(2023, 3, 1), None, "z.htm"),
    ]
    current, prior = latest_pair(filings, "10-K")
    assert current.accession_no == "c25"
    assert prior is not None and prior.accession_no == "c24"


def test_latest_pair_with_single_filing() -> None:
    filings = [FilingMeta("only", "10-K", date(2025, 3, 1), None, "x.htm")]
    current, prior = latest_pair(filings, "10-K")
    assert current.accession_no == "only"
    assert prior is None
