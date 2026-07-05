"""DB schema + seed integration."""

from __future__ import annotations

from pathlib import Path

from windvane.db import connect, init_schema
from windvane.db.connection import seed_universe
from windvane.universe import FIXTURES


def test_init_creates_tables_and_indexes(tmp_db_path: Path) -> None:
    init_schema(tmp_db_path)
    with connect(tmp_db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    table_names = {r["name"] for r in rows}
    expected = {
        "tickers",
        "filings",
        "scores",
        "insights",
        "backtest_results",
        "schema_meta",
    }
    missing = expected - table_names
    assert not missing, f"Missing tables: {missing}"


def test_seed_universe_inserts_fixtures(tmp_db_path: Path) -> None:
    init_schema(tmp_db_path)
    n = seed_universe(tmp_db_path, FIXTURES)
    assert n == 12

    with connect(tmp_db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM tickers").fetchone()
        assert row["c"] == 12

        positive = conn.execute(
            "SELECT COUNT(*) AS c FROM tickers WHERE fixture_role='positive'"
        ).fetchone()
        assert positive["c"] == 5


def test_seed_universe_is_idempotent(tmp_db_path: Path) -> None:
    init_schema(tmp_db_path)
    seed_universe(tmp_db_path, FIXTURES)
    seed_universe(tmp_db_path, FIXTURES)  # re-seed
    with connect(tmp_db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM tickers").fetchone()
        assert row["c"] == 12  # still 12, no duplicates


def test_schema_version_recorded(tmp_db_path: Path) -> None:
    init_schema(tmp_db_path)
    with connect(tmp_db_path) as conn:
        row = conn.execute("SELECT value FROM schema_meta WHERE key='version'").fetchone()
        assert row["value"] == "0.2.0"
