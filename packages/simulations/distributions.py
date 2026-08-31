"""Severity distribution samplers (Milestone 6). Deliberately stdlib-only —
`random` and `statistics.NormalDist` cover everything needed here without
pulling in numpy/scipy for a prototype-scale Monte Carlo engine.

Every sampler takes a `random.Random` instance (never the global `random`
module) so a run's reproducibility depends only on the seed it was given,
never on process-wide RNG state.
"""

from __future__ import annotations

import enum
import math
import random


class DistributionType(str, enum.Enum):
    TRIANGULAR = "triangular"
    PERT = "pert"
    LOGNORMAL = "lognormal"


def sample_triangular(rng: random.Random, low: float, most_likely: float, high: float) -> float:
    return rng.triangular(low, high, most_likely)


def sample_pert(
    rng: random.Random, low: float, most_likely: float, high: float, lambda_: float = 4.0
) -> float:
    """Beta-PERT: a Beta distribution reshaped so its mean lands at the
    classic PERT weighting (low + 4*most_likely + high) / 6, scaled to
    [low, high]. `lambda_` controls how sharply probability concentrates
    around `most_likely` (4 is the standard PERT value)."""
    if high == low:
        return low
    alpha = 1.0 + lambda_ * (most_likely - low) / (high - low)
    beta = 1.0 + lambda_ * (high - most_likely) / (high - low)
    fraction = rng.betavariate(alpha, beta)
    return low + fraction * (high - low)


def sample_lognormal(rng: random.Random, low: float, most_likely: float, high: float) -> float:
    """No closed-form mapping from (min, most likely, max) to a lognormal
    exists — a lognormal has no hard upper bound. This prototype treats
    `most_likely` as the distribution's median (mu = ln(most_likely)) and
    calibrates sigma so `high` lands at the 95th percentile. `low` is
    accepted for interface symmetry with the other two distributions but
    is not used: a lognormal's support starts at 0, not at an arbitrary
    minimum. This is a deliberate, documented simplification (see the
    Milestone 6 plan), not a general-purpose lognormal fit.
    """
    if most_likely <= 0 or high <= most_likely:
        raise ValueError("lognormal requires 0 < most_likely < high")
    mu = math.log(most_likely)
    z_95 = 1.6448536269514722  # NormalDist().inv_cdf(0.95), inlined to avoid recomputation
    sigma = (math.log(high) - mu) / z_95
    return rng.lognormvariate(mu, sigma)


SAMPLERS = {
    DistributionType.TRIANGULAR: sample_triangular,
    DistributionType.PERT: sample_pert,
    DistributionType.LOGNORMAL: sample_lognormal,
}


def sample_severity(
    rng: random.Random, distribution_type: DistributionType, low: float, most_likely: float, high: float
) -> float:
    return SAMPLERS[distribution_type](rng, low, most_likely, high)


def sample_poisson(rng: random.Random, mean: float) -> int:
    """Knuth's algorithm — exact for the small means (annual event
    frequencies) this engine deals with, no numpy required."""
    if mean <= 0:
        return 0
    limit = math.exp(-mean)
    k = 0
    p = 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= limit:
            return k - 1
