"""S&P 500 universe CSV parsing."""

from __future__ import annotations

from pathlib import Path

from windvane.universe import (
    SEED_CSV_PATH,
    _normalize_symbol,
    _parse_constituents_csv,
    load_sp500_universe,
)

SAMPLE_CSV = """Symbol,Security,GICS Sector,GICS Sub-Industry,Headquarters Location,Date added,CIK,Founded
MMM,3M,Industrials,Industrial Conglomerates,"Saint Paul, Minnesota",1957-03-04,66740,1902
BRK.B,Berkshire Hathaway,Financials,Multi-Sector Holdings,"Omaha, Nebraska",2010-02-16,1067983,1839
SNAP,Snap Inc,Communication Services,Interactive Media,"Santa Monica, California",,1564408,2011
BADROW,No CIK Co,Tech,Sub,"X, Y",,,2000
"""


def test_parse_basic_columns() -> None:
    rows = _parse_constituents_csv(SAMPLE_CSV)
    # BADROW dropped (no numeric CIK)
    assert len(rows) == 3
    mmm = rows[0]
    assert mmm.symbol == "MMM"
    assert mmm.cik == "0000066740"  # zero-padded to 10
    assert mmm.name == "3M"
    assert mmm.sector == "Industrials"


def test_share_class_symbol_normalized() -> None:
    rows = _parse_constituents_csv(SAMPLE_CSV)
    brk = next(r for r in rows if r.symbol.startswith("BRK"))
    assert brk.symbol == "BRK-B"  # '.' → '-' for EDGAR/yfinance


def test_fixture_role_injected_for_known_symbols() -> None:
    rows = _parse_constituents_csv(SAMPLE_CSV)
    snap = next(r for r in rows if r.symbol == "SNAP")
    assert snap.fixture_role == "positive"  # SNAP is a fixture
    mmm = next(r for r in rows if r.symbol == "MMM")
    assert mmm.fixture_role == ""  # plain universe member


def test_normalize_symbol() -> None:
    assert _normalize_symbol(" brk.b ") == "BRK-B"
    assert _normalize_symbol("AAPL") == "AAPL"


def test_seed_csv_is_packaged_and_loads() -> None:
    """The packaged seed must exist and parse to roughly the full index."""
    assert SEED_CSV_PATH.exists(), "packaged seed CSV missing"
    rows = _parse_constituents_csv(SEED_CSV_PATH.read_text(encoding="utf-8"))
    assert len(rows) >= 490  # ~503, allow for occasional CIK gaps


def test_load_falls_back_to_seed_when_no_cache(tmp_path: Path) -> None:
    missing_cache = tmp_path / "nonexistent.csv"
    rows = load_sp500_universe(missing_cache, refresh=False)
    assert len(rows) >= 490
