"""Pure helpers for tool latency percentiles (MySQL / SQLite; no PG ordered-set aggregates)."""

from __future__ import annotations

import math


def percentile_linear_sorted(sorted_vals: list[float], p: float) -> float:
    """Linear interpolation percentile; ``sorted_vals`` must be sorted ascending."""
    if not sorted_vals:
        return 0.0
    n = len(sorted_vals)
    if n == 1:
        return float(sorted_vals[0])
    rank = (n - 1) * p
    lo = int(math.floor(rank))
    hi = int(math.ceil(rank))
    if lo == hi:
        return float(sorted_vals[lo])
    frac = rank - lo
    return float(sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac)
