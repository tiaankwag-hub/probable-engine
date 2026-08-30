"""Executive dashboard aggregation.

Milestone 2 scoped this to what the domain model supported at the time:
risk counts/bands, the 5x5 heatmap, category exposure, velocity mix, and a
leadership-attention list. Milestone 3 adds the three KPIs that were
explicitly deferred rather than faked (Weak Controls, Overdue Actions,
Risks Outside Appetite — see docs/architecture/milestone-2-plan.md) now
that Controls, Actions, and Appetite exist. Emerging Risks stays deferred
to Milestone 9.

Lives in packages/shared (not apps/api) because apps/mcp's future
`get_top_risks` tool and any later reporting job will want the same
aggregation logic, not a re-implementation.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.shared.governance_service import compute_appetite_statuses, get_overdue_actions, get_weak_controls
from packages.shared.models.identity import User
from packages.shared.models.risk import Risk, RiskBand, RiskCategory, RiskStatus

TOP_RISKS_LIMIT = 10


def _band_rank(band: RiskBand | None) -> int:
    order = {RiskBand.LOW: 0, RiskBand.MODERATE: 1, RiskBand.HIGH: 2, RiskBand.EXTREME: 3}
    return order.get(band, -1)


def round_to_grid(value: float | None) -> int | None:
    """Rounds a 1.0-5.0 continuous score to the nearest integer grid line
    (1-5) for heatmap placement, clamping to the valid range."""
    if value is None:
        return None
    rounded = round(value)
    return max(1, min(5, rounded))


def compute_executive_dashboard(session: Session, *, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()

    risks = session.scalars(
        select(Risk).where(Risk.status != RiskStatus.CLOSED)
    ).all()

    total_risks = len(risks)
    band_counts: dict[str, int] = {"low": 0, "moderate": 0, "high": 0, "extreme": 0}
    unscored_count = 0
    overdue_reviews_count = 0
    velocity_counts: dict[str, int] = {}
    category_totals: dict[str | None, dict[str, Any]] = {}
    heatmap_counts: dict[tuple[int, int], dict[str, Any]] = {}

    category_names = {
        c.id: c.name for c in session.scalars(select(RiskCategory)).all()
    }
    owner_emails = {u.id: u.email for u in session.scalars(select(User)).all()}

    for risk in risks:
        if risk.residual_band is not None:
            band_counts[risk.residual_band.value] += 1
        else:
            unscored_count += 1

        if risk.next_review_date is not None and risk.next_review_date < today:
            overdue_reviews_count += 1

        if risk.velocity:
            velocity_counts[risk.velocity] = velocity_counts.get(risk.velocity, 0) + 1

        cat_key = risk.category_id
        cat_name = category_names.get(cat_key, "Uncategorized")
        bucket = category_totals.setdefault(
            cat_key, {"category_name": cat_name, "count": 0, "score_sum": 0.0, "score_n": 0}
        )
        bucket["count"] += 1
        if risk.residual_score is not None:
            bucket["score_sum"] += risk.residual_score
            bucket["score_n"] += 1

        grid_likelihood = round_to_grid(risk.likelihood)
        grid_impact = round_to_grid(risk.overall_impact)
        if grid_likelihood is not None and grid_impact is not None:
            cell = heatmap_counts.setdefault(
                (grid_likelihood, grid_impact), {"count": 0, "band_rank": -1, "band": None}
            )
            cell["count"] += 1
            rank = _band_rank(risk.residual_band)
            if rank > cell["band_rank"]:
                cell["band_rank"] = rank
                cell["band"] = risk.residual_band.value if risk.residual_band else None

    band_distribution = [{"band": band, "count": count} for band, count in band_counts.items()]

    category_exposure = [
        {
            "category_id": cat_id,
            "category_name": data["category_name"],
            "risk_count": data["count"],
            "avg_residual_score": (
                round(data["score_sum"] / data["score_n"], 2) if data["score_n"] else None
            ),
        }
        for cat_id, data in sorted(
            category_totals.items(), key=lambda kv: kv[1]["count"], reverse=True
        )
    ]

    velocity_distribution = [
        {"velocity": velocity, "count": count}
        for velocity, count in sorted(velocity_counts.items(), key=lambda kv: kv[1], reverse=True)
    ]

    heatmap = [
        {
            "likelihood": likelihood,
            "impact": impact,
            "count": heatmap_counts.get((likelihood, impact), {}).get("count", 0),
            "dominant_band": heatmap_counts.get((likelihood, impact), {}).get("band"),
        }
        for likelihood in range(1, 6)
        for impact in range(1, 6)
    ]

    top_risks_sorted = sorted(
        (r for r in risks if r.residual_score is not None),
        key=lambda r: r.residual_score,
        reverse=True,
    )[:TOP_RISKS_LIMIT]
    top_risks = [
        {
            "id": r.id,
            "risk_code": r.risk_code,
            "title": r.title,
            "category_name": category_names.get(r.category_id),
            "residual_score": r.residual_score,
            "residual_band": r.residual_band.value if r.residual_band else None,
            "owner_email": owner_emails.get(r.owner_id),
            "next_review_date": r.next_review_date.isoformat() if r.next_review_date else None,
        }
        for r in top_risks_sorted
    ]

    weak_controls_count = len(get_weak_controls(session))
    overdue_actions_count = len(get_overdue_actions(session, today=today))
    appetite_statuses = compute_appetite_statuses(session, risks, today=today)
    risks_outside_appetite_count = sum(
        1 for s in appetite_statuses.values() if s in ("outside_appetite", "material_breach")
    )

    return {
        "total_risks": total_risks,
        "extreme_count": band_counts["extreme"],
        "high_count": band_counts["high"],
        "moderate_count": band_counts["moderate"],
        "low_count": band_counts["low"],
        "unscored_count": unscored_count,
        "overdue_reviews_count": overdue_reviews_count,
        "weak_controls_count": weak_controls_count,
        "overdue_actions_count": overdue_actions_count,
        "risks_outside_appetite_count": risks_outside_appetite_count,
        "band_distribution": band_distribution,
        "category_exposure": category_exposure,
        "velocity_distribution": velocity_distribution,
        "heatmap": heatmap,
        "top_risks": top_risks,
    }
