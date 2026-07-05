"""SQLite-backed rolling window of `raw_strength_critiqued` scores."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from windvane.db import connect
from windvane.scoring.gaussian import ScoringStats, compute_stats, percentile, z_score


@dataclass(frozen=True)
class ScoredFiling:
    """Result of scoring one filing against the rolling window."""

    score_id: int
    symbol: str
    filing_accession: str
    raw_strength: float
    raw_strength_critiqued: float
    z_score: float
    percentile: float
    stats: ScoringStats


def fetch_recent_scores(conn: sqlite3.Connection, *, window_size: int = 200) -> list[float]:
    """Most recent `window_size` scores, newest first.

    Returns just the raw_strength_critiqued values — the rolling window math
    only needs the scalar series.
    """
    rows = conn.execute(
        "SELECT raw_strength_critiqued FROM scores ORDER BY scored_at DESC, id DESC LIMIT ?",
        (window_size,),
    ).fetchall()
    return [r["raw_strength_critiqued"] for r in rows]


def record_score(
    db_path: Path,
    *,
    symbol: str,
    filing_accession: str,
    compared_against: str | None,
    raw_strength: float,
    raw_strength_critiqued: float,
    window_size: int = 200,
    cold_start_mu: float = 0.30,
    cold_start_sigma: float = 0.15,
    cold_start_threshold: int = 30,
) -> ScoredFiling:
    """Score a filing against the current rolling window and persist it.

    The function is atomic: in a single transaction it (1) reads the
    rolling window, (2) computes z/percentile, (3) inserts the new row,
    (4) updates tickers.last_score_id. Pool entry decision is made
    by the caller based on the returned z_score.
    """
    with connect(db_path) as conn:
        conn.execute("BEGIN")
        try:
            recent = fetch_recent_scores(conn, window_size=window_size)
            stats = compute_stats(
                recent,
                cold_start_mu=cold_start_mu,
                cold_start_sigma=cold_start_sigma,
                cold_start_threshold=cold_start_threshold,
            )
            z = z_score(raw_strength_critiqued, stats)
            pct = percentile(raw_strength_critiqued, stats)

            cur = conn.execute(
                """
                INSERT INTO scores (
                    symbol, filing_accession, compared_against_accession,
                    raw_strength, raw_strength_critiqued, z_score, percentile,
                    window_mu, window_sigma, window_size_at_scoring
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol,
                    filing_accession,
                    compared_against,
                    raw_strength,
                    raw_strength_critiqued,
                    z,
                    pct,
                    stats.mu,
                    stats.sigma,
                    stats.window_size,
                ),
            )
            score_id = cur.lastrowid
            assert score_id is not None

            conn.execute(
                "UPDATE tickers SET last_score_id = ? WHERE symbol = ?",
                (score_id, symbol),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    return ScoredFiling(
        score_id=score_id,
        symbol=symbol,
        filing_accession=filing_accession,
        raw_strength=raw_strength,
        raw_strength_critiqued=raw_strength_critiqued,
        z_score=z,
        percentile=pct,
        stats=stats,
    )


def enter_pool_if_triggered(
    db_path: Path,
    scored: ScoredFiling,
    *,
    z_threshold: float = 2.0,
) -> bool:
    """If z ≥ threshold, mark ticker as pool entry. Returns True if entered."""
    if scored.z_score < z_threshold:
        return False
    with connect(db_path) as conn:
        conn.execute(
            "UPDATE tickers SET pool_status = 'pool', "
            "entered_pool_at = COALESCE(entered_pool_at, CURRENT_TIMESTAMP) "
            "WHERE symbol = ?",
            (scored.symbol,),
        )
    return True
