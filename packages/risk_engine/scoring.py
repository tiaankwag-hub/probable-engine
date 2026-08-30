"""Deterministic, config-driven risk scoring (ADR 0007).

Pure functions only — no database session, no HTTP, no AI. Every threshold
and weight comes from a `ScoringConfigData` instance (persisted as
`scoring_config.config` in the database) rather than being hard-coded here,
so scoring can be corrected by changing configuration, not by shipping code.

AI never calls into this module's outputs as an input to override them, and
this module never calls `packages.ai` — the two are intentionally decoupled
(ADR 0006).
"""

from __future__ import annotations

from dataclasses import dataclass, field

DIMENSIONS = (
    "financial",
    "customer_service",
    "operational_delivery",
    "legal_regulatory",
    "reputation",
    "health_safety",
)

MIN_SCALE_VALUE = 1
MAX_SCALE_VALUE = 5


@dataclass(frozen=True)
class ImpactScores:
    financial: int
    customer_service: int
    operational_delivery: int
    legal_regulatory: int
    reputation: int
    health_safety: int

    def as_dict(self) -> dict[str, int]:
        return {dim: getattr(self, dim) for dim in DIMENSIONS}

    def __post_init__(self) -> None:
        for dim, value in self.as_dict().items():
            _validate_scale_value(value, field_name=dim)


@dataclass(frozen=True)
class ScoringConfigData:
    version: int
    dimension_weights: dict[str, float]
    band_thresholds: tuple[tuple[float, str], ...]
    """Ascending (upper_bound_inclusive, band_name) pairs. The last entry's
    upper_bound should be >= the maximum possible score and acts as the
    catch-all band for anything above the second-to-last threshold."""
    max_reduction_fraction: float = 0.6
    max_control_effectiveness: int = 5

    def __post_init__(self) -> None:
        missing = set(DIMENSIONS) - set(self.dimension_weights)
        if missing:
            raise ValueError(f"scoring config missing weights for dimensions: {sorted(missing)}")
        total_weight = sum(self.dimension_weights.values())
        if not (0.999 <= total_weight <= 1.001):
            raise ValueError(f"dimension weights must sum to 1.0, got {total_weight}")
        if not self.band_thresholds:
            raise ValueError("band_thresholds must not be empty")
        bounds = [b for b, _ in self.band_thresholds]
        if bounds != sorted(bounds):
            raise ValueError("band_thresholds must be sorted ascending by upper bound")


@dataclass(frozen=True)
class ScoringResult:
    scoring_config_version: int
    overall_impact: float
    inherent_score: float
    inherent_band: str
    control_effectiveness: int | None
    reduction_fraction: float
    residual_score: float
    residual_band: str


def default_scoring_config() -> ScoringConfigData:
    """The Milestone-1 seed configuration. Equal weighting across all six
    impact dimensions; thresholds chosen so a 5x5 (impact x likelihood)
    matrix maps onto four bands. Administrators can supersede this with a
    new version through the scoring-config API (Milestone 3)."""
    equal_weight = 1.0 / len(DIMENSIONS)
    return ScoringConfigData(
        version=1,
        dimension_weights={dim: equal_weight for dim in DIMENSIONS},
        band_thresholds=(
            (6.0, "low"),
            (12.0, "moderate"),
            (18.0, "high"),
            (25.0, "extreme"),
        ),
        max_reduction_fraction=0.6,
        max_control_effectiveness=5,
    )


def _validate_scale_value(value: int, *, field_name: str) -> None:
    if not (MIN_SCALE_VALUE <= value <= MAX_SCALE_VALUE):
        raise ValueError(
            f"{field_name} must be between {MIN_SCALE_VALUE} and {MAX_SCALE_VALUE}, got {value}"
        )


def compute_overall_impact(scores: ImpactScores, config: ScoringConfigData) -> float:
    weighted_sum = sum(
        getattr(scores, dim) * config.dimension_weights[dim] for dim in DIMENSIONS
    )
    return round(weighted_sum, 2)


def compute_inherent_score(overall_impact: float, likelihood: int) -> float:
    _validate_scale_value(likelihood, field_name="likelihood")
    return round(overall_impact * likelihood, 2)


def band_for_score(score: float, config: ScoringConfigData) -> str:
    for upper_bound, band in config.band_thresholds:
        if score <= upper_bound:
            return band
    return config.band_thresholds[-1][1]


def compute_reduction_fraction(
    control_effectiveness: int | None, config: ScoringConfigData
) -> float:
    if control_effectiveness is None:
        return 0.0
    _validate_scale_value(control_effectiveness, field_name="control_effectiveness")
    return round(
        (control_effectiveness / config.max_control_effectiveness)
        * config.max_reduction_fraction,
        4,
    )


def compute_residual_score(
    inherent_score: float, control_effectiveness: int | None, config: ScoringConfigData
) -> tuple[float, float]:
    """Returns (residual_score, reduction_fraction)."""
    reduction_fraction = compute_reduction_fraction(control_effectiveness, config)
    residual = round(inherent_score * (1 - reduction_fraction), 2)
    return residual, reduction_fraction


def score_risk(
    scores: ImpactScores,
    likelihood: int,
    control_effectiveness: int | None,
    config: ScoringConfigData | None = None,
) -> ScoringResult:
    """The single entry point apps/api and apps/worker should call. Given raw
    inputs and a config, returns every derived field `risks`/`risk_assessments`
    stores. Deterministic: identical inputs always produce identical output.
    """
    config = config or default_scoring_config()

    overall_impact = compute_overall_impact(scores, config)
    inherent_score = compute_inherent_score(overall_impact, likelihood)
    inherent_band = band_for_score(inherent_score, config)
    residual_score, reduction_fraction = compute_residual_score(
        inherent_score, control_effectiveness, config
    )
    residual_band = band_for_score(residual_score, config)

    return ScoringResult(
        scoring_config_version=config.version,
        overall_impact=overall_impact,
        inherent_score=inherent_score,
        inherent_band=inherent_band,
        control_effectiveness=control_effectiveness,
        reduction_fraction=reduction_fraction,
        residual_score=residual_score,
        residual_band=residual_band,
    )
