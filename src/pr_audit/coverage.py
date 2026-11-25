"""Turn a requirement x hunk relevance matrix into verdict features. Pure code, no model.

Idea: `done` = every requirement has a strongly relevant hunk; `partial` = some requirements are
uncovered; `missing` = none are. Hunks that no requirement claims are orphans (scope-creep candidates).
"""
from __future__ import annotations
from statistics import mean

THRESHOLDS = (0.3, 0.5, 0.7)


def best_per_req(m: list[list[float]]) -> list[float]:
    return [max(row) if row else 0.0 for row in m]


def best_per_hunk(m: list[list[float]]) -> list[float]:
    if not m or not m[0]:
        return []
    return [max(m[r][h] for r in range(len(m))) for h in range(len(m[0]))]


def orphan_flags(m: list[list[float]], thr: float = 0.5) -> list[bool]:
    return [s < thr for s in best_per_hunk(m)]


FEATURE_NAMES = (["n_req", "n_hunk", "min_best", "mean_best", "max_best", "hunk_mean_best"]
                 + [f"frac_req_cov_{t}" for t in THRESHOLDS] + [f"orphan_frac_{t}" for t in THRESHOLDS])


def features(m: list[list[float]]) -> list[float]:
    bq, bh = best_per_req(m), best_per_hunk(m)
    if not bq or not bh:
        return [0.0] * len(FEATURE_NAMES)
    f = [len(bq), len(bh), min(bq), mean(bq), max(bq), mean(bh)]
    f += [sum(b >= t for b in bq) / len(bq) for t in THRESHOLDS]
    f += [sum(b < t for b in bh) / len(bh) for t in THRESHOLDS]
    return f
