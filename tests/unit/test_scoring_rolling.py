"""Rolling-window persistence & pool-entry tests."""

from __future__ import annotations

from pathlib import Path

from windvane.db import connect, init_schema
from windvane.db.connection import seed_universe
from windvane.scoring.rolling_window import (
    enter_pool_if_triggered,
    fetch_recent_scores,
    record_score,
)
from windvane.universe import FIXTURES


def _setup(tmp_db_path: Path) -> Path:
    init_schema(tmp_db_path)
    seed_universe(tmp_db_path, FIXTURES)
    return tmp_db_path


def _add_filing(db_path: Path, symbol: str, accession: str, form: str = "10-K") -> None:
    """Insert a dummy filing row to satisfy FK from scores."""
    with connect(db_path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO filings "
            "(accession_no, symbol, filing_type, filing_date) "
            "VALUES (?, ?, ?, '2025-01-01')",
            (accession, symbol, form),
        )


def test_record_score_inserts_and_returns_z(tmp_db_path: Path) -> None:
    db = _setup(tmp_db_path)
    _add_filing(db, "DOCU", "acc-001")
    _add_filing(db, "DOCU", "acc-prior")
    scored = record_score(
        db,
        symbol="DOCU",
        filing_accession="acc-001",
        compared_against="acc-prior",
        raw_strength=0.65,
        raw_strength_critiqued=0.60,
    )
    # Cold start: μ=0.30 σ=0.15. (0.60-0.30)/0.15 = 2.0
    assert scored.z_score == 2.0
    assert scored.stats.is_cold_start
    assert scored.score_id > 0


def test_record_score_updates_last_score_id(tmp_db_path: Path) -> None:
    db = _setup(tmp_db_path)
    _add_filing(db, "DOCU", "acc-001")
    scored = record_score(
        db,
        symbol="DOCU",
        filing_accession="acc-001",
        compared_against=None,
        raw_strength=0.5,
        raw_strength_critiqued=0.45,
    )
    with connect(db) as conn:
        row = conn.execute("SELECT last_score_id FROM tickers WHERE symbol='DOCU'").fetchone()
    assert row["last_score_id"] == scored.score_id


def test_fetch_recent_scores_orders_newest_first(tmp_db_path: Path) -> None:
    db = _setup(tmp_db_path)
    for i, raw in enumerate([0.1, 0.2, 0.3]):
        _add_filing(db, "DOCU", f"acc-{i}")
        record_score(
            db,
            symbol="DOCU",
            filing_accession=f"acc-{i}",
            compared_against=None,
            raw_strength=raw,
            raw_strength_critiqued=raw,
        )
    with connect(db) as conn:
        recent = fetch_recent_scores(conn, window_size=10)
    # Newest first: 0.3, 0.2, 0.1
    assert recent == [0.3, 0.2, 0.1]


def test_pool_entry_at_or_above_threshold(tmp_db_path: Path) -> None:
    db = _setup(tmp_db_path)
    _add_filing(db, "DOCU", "acc-001")
    scored = record_score(
        db,
        symbol="DOCU",
        filing_accession="acc-001",
        compared_against=None,
        raw_strength=0.7,
        raw_strength_critiqued=0.62,
    )
    # z = (0.62 - 0.30) / 0.15 ≈ 2.133
    entered = enter_pool_if_triggered(db, scored, z_threshold=2.0)
    assert entered is True

    with connect(db) as conn:
        row = conn.execute("SELECT pool_status FROM tickers WHERE symbol='DOCU'").fetchone()
    assert row["pool_status"] == "pool"


def test_no_pool_entry_below_threshold(tmp_db_path: Path) -> None:
    db = _setup(tmp_db_path)
    _add_filing(db, "KO", "acc-001")
    scored = record_score(
        db,
        symbol="KO",
        filing_accession="acc-001",
        compared_against=None,
        raw_strength=0.30,
        raw_strength_critiqued=0.30,
    )
    # z = 0
    entered = enter_pool_if_triggered(db, scored, z_threshold=2.0)
    assert entered is False

    with connect(db) as conn:
        row = conn.execute("SELECT pool_status FROM tickers WHERE symbol='KO'").fetchone()
    assert row["pool_status"] == "screening"


def test_rolling_window_caps_at_size(tmp_db_path: Path) -> None:
    db = _setup(tmp_db_path)
    # Insert 5 scores; window_size=3 should return only 3 most recent
    for i in range(5):
        _add_filing(db, "DOCU", f"acc-{i}")
        record_score(
            db,
            symbol="DOCU",
            filing_accession=f"acc-{i}",
            compared_against=None,
            raw_strength=0.1 * i,
            raw_strength_critiqued=0.1 * i,
        )
    with connect(db) as conn:
        recent = fetch_recent_scores(conn, window_size=3)
    assert len(recent) == 3
    # newest three are i=4 (0.4), i=3 (0.3), i=2 (0.2)
    import pytest

    assert recent == pytest.approx([0.4, 0.3, 0.2])
