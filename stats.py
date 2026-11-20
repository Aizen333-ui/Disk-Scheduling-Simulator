"""Small statistics helpers (no external dependencies)."""

import math
from typing import Dict, List, Sequence, Tuple

# Two-sided 95% critical values of Student's t distribution, by degrees of freedom.
_T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306,
        9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
        16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086, 21: 2.080, 22: 2.074,
        23: 2.069, 24: 2.064, 25: 2.060, 26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042}


def t_critical(df: int) -> float:
    if df < 1:
        raise ValueError("Degrees of freedom must be at least 1.")
    if df in _T95:
        return _T95[df]
    if df <= 60:
        return 2.000
    if df <= 120:
        return 1.980
    return 1.960


def mean(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("No values.")
    return sum(values) / len(values)


def stdev(values: Sequence[float]) -> float:
    """Sample standard deviation (0 for a single value)."""
    n = len(values)
    if n < 2:
        return 0.0
    m = mean(values)
    return math.sqrt(sum((x - m) ** 2 for x in values) / (n - 1))


def ci95(values: Sequence[float]) -> Tuple[float, float]:
    """Return (mean, half-width of the 95% confidence interval for the mean)."""
    n = len(values)
    m = mean(values)
    if n < 2:
        return m, 0.0
    return m, t_critical(n - 1) * stdev(values) / math.sqrt(n)


def percentile(values: Sequence[float], p: float) -> float:
    """p in 0..100, linear interpolation between closest ranks."""
    if not values:
        raise ValueError("No values.")
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    k = (len(xs) - 1) * p / 100.0
    lo, hi = math.floor(k), math.ceil(k)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def summarize(values_by_algo: Dict[str, List[float]]) -> Dict[str, Tuple[float, float, float]]:
    """name -> (mean, 95% CI half-width, sample standard deviation)."""
    out = {}
    for name, values in values_by_algo.items():
        m, half = ci95(values)
        out[name] = (m, half, stdev(values))
    return out
