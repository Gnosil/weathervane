"""Rolling-window Gaussian z-score math.

Design (spec §4):
- raw_strength ∈ [0, 1] from stage-2 critique
- rolling window = last N scores (default 200)
- cold start (< K samples, default K=30): use prior μ=0.30, σ=0.15
- z = (raw - μ) / σ
- z ≥ 2 → enter pool (single-tail ≈ 2.3%)
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import NormalDist, fmean, pstdev


@dataclass(frozen=True)
class ScoringStats:
    """Snapshot of the rolling window at scoring time."""

    mu: float
    sigma: float
    window_size: int
    is_cold_start: bool


def compute_stats(
    scores: list[float],
    *,
    cold_start_mu: float = 0.30,
    cold_start_sigma: float = 0.15,
    cold_start_threshold: int = 30,
) -> ScoringStats:
    """Return μ, σ for the rolling window.

    Below the cold-start threshold, return the prior; above it, use the
    empirical mean / population std. We use population std (pstdev) rather
    than sample std because the window IS the population we're judging
    against.
    """
    n = len(scores)
    if n < cold_start_threshold:
        return ScoringStats(
            mu=cold_start_mu,
            sigma=cold_start_sigma,
            window_size=n,
            is_cold_start=True,
        )
    sigma = pstdev(scores)
    if sigma <= 0:
        # Degenerate (all-equal window) — fall back to prior σ to avoid div0.
        sigma = cold_start_sigma
    return ScoringStats(
        mu=fmean(scores),
        sigma=sigma,
        window_size=n,
        is_cold_start=False,
    )


def z_score(raw: float, stats: ScoringStats) -> float:
    """Standardized z-score against the rolling window."""
    if stats.sigma <= 0:
        return 0.0
    return (raw - stats.mu) / stats.sigma


def percentile(raw: float, stats: ScoringStats) -> float:
    """Normal-CDF percentile (0-100)."""
    if stats.sigma <= 0:
        return 50.0
    return NormalDist(mu=stats.mu, sigma=stats.sigma).cdf(raw) * 100.0


def distribution_snapshot(scores: list[float], bins: int = 10) -> list[int]:
    """Histogram of [0, 1] across `bins` equal-width buckets."""
    if bins <= 0:
        raise ValueError("bins must be positive")
    hist = [0] * bins
    for s in scores:
        idx = int(s * bins)
        if idx >= bins:
            idx = bins - 1
        if idx < 0:
            idx = 0
        hist[idx] += 1
    return hist
