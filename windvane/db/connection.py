"""SQLite connection + schema bootstrap."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA_FILE = Path(__file__).parent / "schema.sql"


@contextmanager
def connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    """Open a SQLite connection, ensuring foreign keys & WAL.

    Yields a connection; auto-closes on exit. Caller is responsible
    for committing transactions.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        db_path,
        detect_types=sqlite3.PARSE_DECLTYPES,
        isolation_level=None,  # autocommit; use BEGIN/COMMIT explicitly
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
    finally:
        conn.close()


def init_schema(db_path: Path) -> None:
    """Create all tables if not present, then run lightweight migrations. Idempotent."""
    sql = SCHEMA_FILE.read_text(encoding="utf-8")
    with connect(db_path) as conn:
        conn.executescript(sql)
        _migrate(conn)


def _migrate(conn: sqlite3.Connection) -> None:
    """Additive, idempotent column migrations for already-initialized DBs."""
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(tickers)")}
    if "sector" not in existing:
        conn.execute("ALTER TABLE tickers ADD COLUMN sector TEXT")



def seed_universe(db_path: Path, tickers: list) -> int:
    """Insert/upsert tickers. Returns rows inserted/updated.

    Preserves an existing fixture_role when the incoming ticker has none
    (so loading the full S&P 500 universe never clobbers the 12 fixtures'
    role labels).
    """
    count = 0
    with connect(db_path) as conn:
        for t in tickers:
            sector = getattr(t, "sector", None) or None
            role = getattr(t, "fixture_role", None) or None
            conn.execute(
                """
                INSERT INTO tickers (symbol, cik, name, sector, in_sp500, fixture_role)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    cik=excluded.cik,
                    name=excluded.name,
                    sector=COALESCE(excluded.sector, tickers.sector),
                    in_sp500=excluded.in_sp500,
                    fixture_role=COALESCE(excluded.fixture_role, tickers.fixture_role)
                """,
                (t.symbol, t.cik, t.name, sector, 1, role),
            )
            count += 1
    return count
