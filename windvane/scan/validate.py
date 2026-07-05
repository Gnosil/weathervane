"""Identification-accuracy validation for the pivot scorer.

NOT a profit/accuracy-rate claim. This is a small, hand-picked SANITY CHECK
that asks: does the scorer rank known pivots above known stable companies, flag
shells, and does the stage-2 critique deflate buzzword-heavy hard cases?

Ground truth is the EXTERNAL, verifiable label of each name (did it actually
restructure / divest / rebrand vs. run a stable business) — set here from prior
web research and public fact, NOT from a model's opinion.
"""

from __future__ import annotations

from dataclasses import dataclass

# External ground-truth labels (verifiable fact, not model opinion).
#   pivot  = genuine structural/business transformation
#   stable = mature business, no real structural change
#   shell  = drastic change-of-control / change-of-business (rebrand)
#   hard   = heavy transformation NARRATIVE but limited structural change
#            (buzzword test for the critique layer)
GROUND_TRUTH: dict[str, str] = {
    "HON": "pivot", "DOCU": "pivot", "NET": "pivot", "SNAP": "pivot", "TWLO": "pivot",
    "KO": "stable", "PG": "stable", "JNJ": "stable", "WMT": "stable", "JPM": "stable",
    "BIRD": "shell", "CAPS": "shell",
    "IBM": "hard", "CSCO": "hard",
}


@dataclass
class Sample:
    symbol: str
    raw: float
    critiqued: float
    label: str


def build_samples(scored: list[dict]) -> list[Sample]:
    out = []
    for r in scored:
        sym = r.get("symbol")
        if sym not in GROUND_TRUTH:
            continue
        out.append(
            Sample(
                symbol=sym,
                raw=float(r.get("raw_strength", 0.0)),
                critiqued=float(r.get("raw_strength_critiqued", 0.0)),
                label=GROUND_TRUTH[sym],
            )
        )
    return out


def group_means(samples: list[Sample]) -> dict[str, float]:
    groups: dict[str, list[float]] = {}
    for s in samples:
        groups.setdefault(s.label, []).append(s.critiqued)
    return {k: sum(v) / len(v) for k, v in groups.items() if v}


def separation(samples: list[Sample]) -> dict:
    """Does the scorer separate pivots from stable names?"""
    pivots = [s.critiqued for s in samples if s.label == "pivot"]
    stable = [s.critiqued for s in samples if s.label == "stable"]
    res = {"n_pivot": len(pivots), "n_stable": len(stable)}
    if pivots and stable:
        res["min_pivot"] = min(pivots)
        res["max_stable"] = max(stable)
        res["clean_separation"] = min(pivots) > max(stable)
        res["gap"] = min(pivots) - max(stable)
    return res


def critique_effect(samples: list[Sample]) -> dict:
    """How much did stage-2 deflate each group (raw -> critiqued)?"""
    out = {}
    by_label: dict[str, list[Sample]] = {}
    for s in samples:
        by_label.setdefault(s.label, []).append(s)
    for label, group in by_label.items():
        deflate = [s.raw - s.critiqued for s in group]
        out[label] = sum(deflate) / len(deflate) if deflate else 0.0
    return out
