"""Gaussian z-score math tests."""

from __future__ import annotations

import math

from windvane.scoring.gaussian import (
    compute_stats,
    distribution_snapshot,
    percentile,
    z_score,
)


def test_cold_start_returns_prior() -> None:
    stats = compute_stats([0.1, 0.2, 0.3], cold_start_threshold=30)
    assert stats.is_cold_start
    assert stats.mu == 0.30
    assert stats.sigma == 0.15
    assert stats.window_size == 3


def test_warm_start_uses_empirical_stats() -> None:
    scores = [0.1] * 15 + [0.5] * 15  # 30 samples
    stats = compute_stats(scores, cold_start_threshold=30)
    assert not stats.is_cold_start
    assert stats.window_size == 30
    assert math.isclose(stats.mu, 0.30, rel_tol=1e-9)
    # pstdev sqrt(0.04) = 0.20
    assert math.isclose(stats.sigma, 0.20, rel_tol=1e-9)


def test_z_score_basic() -> None:
    scores = [0.1] * 15 + [0.5] * 15
    stats = compute_stats(scores)
    z = z_score(0.7, stats)
    # raw=0.7, mu=0.3, sigma=0.2 → z=2.0
    assert math.isclose(z, 2.0, rel_tol=1e-9)


def test_z_threshold_2sigma_corresponds_to_top_2_3_pct() -> None:
    """Calibration check: under the cold-start prior (μ=0.30, σ=0.15),
    a raw of 0.60 sits at z=2 and roughly the 97.7th percentile."""
    stats = compute_stats([])  # cold start
    z = z_score(0.60, stats)
    assert math.isclose(z, 2.0, rel_tol=1e-9)
    pct = percentile(0.60, stats)
    assert 97.0 < pct < 98.0


def test_degenerate_window_falls_back_to_prior_sigma() -> None:
    # All-equal warm window → pstdev=0 → fallback
    scores = [0.3] * 50
    stats = compute_stats(scores, cold_start_sigma=0.15)
    assert not stats.is_cold_start
    assert stats.sigma == 0.15  # fallback applied
    # z should be a finite number
    z = z_score(0.6, stats)
    assert math.isfinite(z)


def test_distribution_snapshot_basic() -> None:
    scores = [0.05, 0.15, 0.25, 0.95]
    hist = distribution_snapshot(scores, bins=10)
    assert len(hist) == 10
    assert hist[0] == 1  # 0.05
    assert hist[1] == 1  # 0.15
    assert hist[2] == 1  # 0.25
    assert hist[9] == 1  # 0.95
    assert sum(hist) == 4


def test_distribution_snapshot_handles_edge_value_1() -> None:
    hist = distribution_snapshot([1.0], bins=10)
    assert hist[-1] == 1  # 1.0 should land in the top bin, not overflow


def test_distribution_snapshot_empty() -> None:
    hist = distribution_snapshot([], bins=10)
    assert hist == [0] * 10
