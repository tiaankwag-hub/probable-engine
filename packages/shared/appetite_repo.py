"""Resolves which `risk_appetite` row applies to a given risk (category +
optional business unit), converting it into the pure
`packages.risk_engine.AppetiteThresholds` the evaluation function expects —
the same database-config-not-hard-coded pattern as
`scoring_config_repo.py` (ADR 0007 extended to appetite).
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.risk_engine.appetite import AppetiteThresholds, evaluate_appetite
from packages.shared.models.risk import Risk
from packages.shared.models.risk_appetite import RiskAppetite


def _specificity(row: RiskAppetite) -> tuple[int, int]:
    """Higher is more specific: an exact category match beats a global
    default, and an exact business-unit match beats a category-wide one."""
    return (1 if row.category_id is not None else 0, 1 if row.business_unit is not None else 0)


def get_applicable_appetite(
    session: Session,
    *,
    category_id: uuid.UUID | None,
    business_unit: str | None,
    today: date | None = None,
) -> RiskAppetite | None:
    today = today or date.today()
    rows = session.scalars(
        select(RiskAppetite).where(
            (RiskAppetite.category_id == category_id) | (RiskAppetite.category_id.is_(None)),
            RiskAppetite.effective_from <= today,
        )
    ).all()

    candidates = [
        row
        for row in rows
        if (row.effective_to is None or row.effective_to >= today)
        and (row.business_unit is None or row.business_unit == business_unit)
    ]
    if not candidates:
        return None
    return max(candidates, key=_specificity)


def to_thresholds(row: RiskAppetite) -> AppetiteThresholds:
    return AppetiteThresholds(
        appetite_band=row.appetite_band,
        tolerance_band=row.tolerance_band,
        limit_value=float(row.limit_value) if row.limit_value is not None else None,
    )


def compute_appetite_status_for_risk(session: Session, risk: Risk) -> str:
    """Convenience wrapper for a single risk (used by the risk-detail
    endpoint). Bulk aggregation (Governance Health) fetches all appetite
    rows once instead of calling this per-risk — see governance_service.py.
    """
    appetite_row = get_applicable_appetite(
        session, category_id=risk.category_id, business_unit=risk.department
    )
    thresholds = to_thresholds(appetite_row) if appetite_row else None
    band = risk.residual_band.value if risk.residual_band else None
    return evaluate_appetite(band, risk.residual_score, thresholds)
