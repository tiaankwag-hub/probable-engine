"""Frequency-severity Monte Carlo engine (Milestone 6) and a lightweight
portfolio correlation layer (Milestone 7).

Each simulated "iteration" is one year: the number of loss events is drawn
from a Poisson distribution parameterized by the config's
`annual_event_frequency`, and each event's severity is drawn independently
from the chosen distribution over (loss_min, loss_most_likely, loss_max).
The annual loss for that iteration is the sum of that year's event
severities (0 if no events occurred) — the standard actuarial
frequency-severity shape, not a single per-iteration draw, so
`annual_event_frequency` actually does something.
"""

from __future__ import annotations

import random
import statistics
from dataclasses import dataclass, field
from typing import Sequence

from packages.simulations.distributions import DistributionType, sample_poisson, sample_severity

HISTOGRAM_BINS = 20


@dataclass(frozen=True)
class SimulationParams:
    distribution_type: DistributionType
    loss_min: float
    loss_most_likely: float
    loss_max: float
    annual_event_frequency: float
    iterations: int
    seed: int


@dataclass(frozen=True)
class SimulationStats:
    expected_annual_loss: float
    median: float
    p75: float
    p90: float
    p95: float
    p99: float
    histogram: list[dict] = field(default_factory=list)


def run_annual_loss_simulation(params: SimulationParams) -> list[float]:
    """Returns one simulated annual loss per iteration. Deterministic for a
    given seed — the only randomness source is the `random.Random(seed)`
    instance created here, never global RNG state."""
    rng = random.Random(params.seed)
    losses = []
    for _ in range(params.iterations):
        event_count = sample_poisson(rng, params.annual_event_frequency)
        annual_loss = sum(
            sample_severity(
                rng, params.distribution_type, params.loss_min, params.loss_most_likely, params.loss_max
            )
            for _ in range(event_count)
        )
        losses.append(annual_loss)
    return losses


def _percentile(sorted_values: Sequence[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    idx = min(len(sorted_values) - 1, max(0, round(p * (len(sorted_values) - 1))))
    return sorted_values[idx]


def build_histogram(values: Sequence[float], bins: int = HISTOGRAM_BINS) -> list[dict]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if lo == hi:
        return [{"bin_start": lo, "bin_end": hi, "count": len(values)}]
    width = (hi - lo) / bins
    counts = [0] * bins
    for v in values:
        idx = min(bins - 1, int((v - lo) / width))
        counts[idx] += 1
    return [
        {"bin_start": lo + i * width, "bin_end": lo + (i + 1) * width, "count": counts[i]}
        for i in range(bins)
    ]


def compute_statistics(annual_losses: Sequence[float]) -> SimulationStats:
    sorted_losses = sorted(annual_losses)
    return SimulationStats(
        expected_annual_loss=statistics.fmean(annual_losses) if annual_losses else 0.0,
        median=_percentile(sorted_losses, 0.50),
        p75=_percentile(sorted_losses, 0.75),
        p90=_percentile(sorted_losses, 0.90),
        p95=_percentile(sorted_losses, 0.95),
        p99=_percentile(sorted_losses, 0.99),
        histogram=build_histogram(annual_losses),
    )


def probability_exceeding(annual_losses: Sequence[float], threshold: float) -> float:
    if not annual_losses:
        return 0.0
    return sum(1 for loss in annual_losses if loss > threshold) / len(annual_losses)


def correlate_series(reference_normals: Sequence[float], series: Sequence[float]) -> list[float]:
    """Iman-Conover rank matching: reorders `series` (leaving its values,
    and therefore its exact marginal distribution, untouched) so its rank
    order matches `reference_normals`'. Two series correlated against the
    same reference end up correlated with each other, without needing an
    inverse-CDF for whichever distribution `series` came from — this is
    what lets Triangular, PERT, and Lognormal risks all be correlated in
    the same portfolio run with one simple technique.
    """
    if len(reference_normals) != len(series):
        raise ValueError("reference_normals and series must be the same length")
    sorted_series = sorted(series)
    rank_order = sorted(range(len(reference_normals)), key=lambda i: reference_normals[i])
    result = [0.0] * len(series)
    for rank, original_index in enumerate(rank_order):
        result[original_index] = sorted_series[rank]
    return result


def generate_reference_normals(
    *, common_seed: int, idiosyncratic_seed: int, correlation_strength: float, iterations: int
) -> list[float]:
    """One risk's correlated reference series: a blend of a systemic factor
    shared by every risk in its correlation group (`common_seed` is the
    same across the whole group) and a risk-specific idiosyncratic factor,
    weighted by `correlation_strength` (0 = independent, 1 = moves in
    lockstep with the group)."""
    common_rng = random.Random(common_seed)
    idio_rng = random.Random(idiosyncratic_seed)
    rho = max(0.0, min(1.0, correlation_strength))
    common_weight = rho**0.5
    idio_weight = (1 - rho) ** 0.5
    return [
        common_weight * common_rng.gauss(0, 1) + idio_weight * idio_rng.gauss(0, 1)
        for _ in range(iterations)
    ]


DEFAULT_CORRELATION_STRENGTH = 0.5


@dataclass(frozen=True)
class RiskSimulationInput:
    risk_id: str
    params: SimulationParams
    correlation_group: str | None = None
    correlation_strength: float | None = None


@dataclass(frozen=True)
class PortfolioResult:
    per_risk_annual_losses: dict[str, list[float]]
    portfolio_annual_losses: list[float]
    portfolio_stats: SimulationStats
    per_risk_contribution: dict[str, float]


def run_portfolio_simulation(
    risk_inputs: Sequence[RiskSimulationInput], *, iterations: int, seed: int
) -> PortfolioResult:
    """Runs every linked risk's own frequency-severity model for the same
    `iterations` years, correlating risks that share a non-null
    `correlation_group` via `correlate_series`, then sums per-iteration
    across all risks for the portfolio total. Reproducible end-to-end from
    one `seed`: every risk and every correlation group derives its own
    seed deterministically from `seed` plus its position in `risk_inputs`
    (never from Python's randomized `hash()`, which would break
    reproducibility across processes).
    """
    per_risk_losses: dict[str, list[float]] = {}
    group_indices: dict[str, list[int]] = {}

    for index, item in enumerate(risk_inputs):
        risk_seed = seed + index + 1
        params = SimulationParams(
            distribution_type=item.params.distribution_type,
            loss_min=item.params.loss_min,
            loss_most_likely=item.params.loss_most_likely,
            loss_max=item.params.loss_max,
            annual_event_frequency=item.params.annual_event_frequency,
            iterations=iterations,
            seed=risk_seed,
        )
        per_risk_losses[item.risk_id] = run_annual_loss_simulation(params)
        if item.correlation_group:
            group_indices.setdefault(item.correlation_group, []).append(index)

    for group_position, (_group_name, indices) in enumerate(sorted(group_indices.items())):
        common_seed = seed + 100_000 + group_position
        for index in indices:
            item = risk_inputs[index]
            risk_seed = seed + index + 1
            rho = (
                item.correlation_strength
                if item.correlation_strength is not None
                else DEFAULT_CORRELATION_STRENGTH
            )
            reference = generate_reference_normals(
                common_seed=common_seed,
                idiosyncratic_seed=risk_seed,
                correlation_strength=rho,
                iterations=iterations,
            )
            per_risk_losses[item.risk_id] = correlate_series(reference, per_risk_losses[item.risk_id])

    portfolio_annual_losses = [
        sum(per_risk_losses[item.risk_id][k] for item in risk_inputs) for k in range(iterations)
    ]
    portfolio_stats = compute_statistics(portfolio_annual_losses)

    tail_threshold = portfolio_stats.p95
    tail_indices = [k for k, loss in enumerate(portfolio_annual_losses) if loss >= tail_threshold]
    tail_avgs = {
        item.risk_id: (
            statistics.fmean(per_risk_losses[item.risk_id][k] for k in tail_indices)
            if tail_indices
            else 0.0
        )
        for item in risk_inputs
    }
    total_tail_avg = sum(tail_avgs.values())
    per_risk_contribution = (
        {risk_id: avg / total_tail_avg for risk_id, avg in tail_avgs.items()}
        if total_tail_avg > 0
        else {risk_id: 1 / len(risk_inputs) for risk_id in tail_avgs}
    )

    return PortfolioResult(
        per_risk_annual_losses=per_risk_losses,
        portfolio_annual_losses=portfolio_annual_losses,
        portfolio_stats=portfolio_stats,
        per_risk_contribution=per_risk_contribution,
    )
