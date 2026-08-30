"""Deterministic risk-appetite evaluation (brief's RISK APPETITE section).

Pure functions only, mirroring the scoring module's shape (ADR 0007's
"nothing hard-coded, everything config-driven" principle extended to
appetite): given a risk's residual band/score and an applicable
`AppetiteThresholds` row (resolved from the database by
`packages.shared.appetite_repo`), returns one of four statuses. AI never
calls into this — appetite status is as deterministic and auditable as
scoring itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

BAND_RANK = {"low": 0, "moderate": 1, "high": 2, "extreme": 3}

AppetiteStatus = Literal[
    "not_configured", "within_appetite", "approaching_tolerance", "outside_appetite", "material_breach"
]


@dataclass(frozen=True)
class AppetiteThresholds:
    appetite_band: str
    """Highest residual band still considered within appetite."""
    tolerance_band: str
    """Highest residual band still considered a tolerated (but watched) excursion."""
    limit_value: float | None = None
    """An absolute residual-score ceiling. Exceeding it is always a material
    breach regardless of band, even if the band itself is only at the
    tolerance line."""

    def __post_init__(self) -> None:
        for field_name in ("appetite_band", "tolerance_band"):
            value = getattr(self, field_name)
            if value not in BAND_RANK:
                raise ValueError(f"{field_name} must be one of {sorted(BAND_RANK)}, got {value!r}")
        if BAND_RANK[self.tolerance_band] < BAND_RANK[self.appetite_band]:
            raise ValueError("tolerance_band must be at or above appetite_band")


def evaluate_appetite(
    residual_band: str | None,
    residual_score: float | None,
    thresholds: AppetiteThresholds | None,
) -> AppetiteStatus:
    if thresholds is None or residual_band is None:
        return "not_configured"

    if (
        thresholds.limit_value is not None
        and residual_score is not None
        and residual_score > thresholds.limit_value
    ):
        return "material_breach"

    risk_rank = BAND_RANK[residual_band]
    if risk_rank <= BAND_RANK[thresholds.appetite_band]:
        return "within_appetite"
    if risk_rank <= BAND_RANK[thresholds.tolerance_band]:
        return "approaching_tolerance"
    return "outside_appetite"
