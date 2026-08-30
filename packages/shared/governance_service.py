"""Governance Health aggregation (Milestone 3): weak controls, overdue
actions, overdue reviews, and appetite-breach status across the register.
Bulk versions of the same appetite lookup `appetite_repo.py` does per-risk,
so this doesn't run one query per risk for a register of any real size.

The Milestone 2 Executive Dashboard's originally-deferred KPIs (Risks
Outside Appetite, Weak Controls, Overdue Actions — see
docs/architecture/milestone-2-plan.md) are backed by these same functions
now that Controls, Actions, and Appetite exist.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.risk_engine.appetite import evaluate_appetite
from packages.shared.appetite_repo import get_applicable_appetite, to_thresholds
from packages.shared.models.action import Action, ActionStatus
from packages.shared.models.control import Control
from packages.shared.models.identity import User
from packages.shared.models.risk import Risk, RiskStatus
from packages.shared.models.risk_appetite import RiskAppetite

WEAK_CONTROL_THRESHOLD = 2
NON_TERMINAL_ACTION_STATUSES = (ActionStatus.OPEN, ActionStatus.IN_PROGRESS)


def get_weak_controls(session: Session, *, threshold: int = WEAK_CONTROL_THRESHOLD) -> list[Control]:
    """A control is 'weak' if its most-recently-known effectiveness rating
    (operating, falling back to design if never tested) is at or below the
    threshold on the 1-5 scale."""
    controls = session.scalars(select(Control)).all()
    weak = []
    for control in controls:
        effectiveness = (
            control.operating_effectiveness
            if control.operating_effectiveness is not None
            else control.design_effectiveness
        )
        if effectiveness is not None and effectiveness <= threshold:
            weak.append(control)
    return weak


def get_overdue_actions(session: Session, *, today: date | None = None) -> list[Action]:
    today = today or date.today()
    return session.scalars(
        select(Action).where(
            Action.due_date < today, Action.status.in_(NON_TERMINAL_ACTION_STATUSES)
        )
    ).all()


def compute_appetite_statuses(
    session: Session, risks: list[Risk], *, today: date | None = None
) -> dict:
    """Bulk appetite evaluation: fetches every risk_appetite row once, then
    matches each risk in Python rather than issuing one query per risk."""
    today = today or date.today()
    appetite_rows = session.scalars(select(RiskAppetite)).all()

    def best_match(category_id, business_unit):
        candidates = [
            row
            for row in appetite_rows
            if (row.category_id == category_id or row.category_id is None)
            and row.effective_from <= today
            and (row.effective_to is None or row.effective_to >= today)
            and (row.business_unit is None or row.business_unit == business_unit)
        ]
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda r: (1 if r.category_id is not None else 0, 1 if r.business_unit is not None else 0),
        )

    statuses = {}
    for risk in risks:
        appetite_row = best_match(risk.category_id, risk.department)
        thresholds = to_thresholds(appetite_row) if appetite_row else None
        band = risk.residual_band.value if risk.residual_band else None
        statuses[risk.id] = evaluate_appetite(band, risk.residual_score, thresholds)
    return statuses


def compute_governance_health(session: Session, *, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()

    risks = session.scalars(select(Risk).where(Risk.status != RiskStatus.CLOSED)).all()
    owner_emails = {u.id: u.email for u in session.scalars(select(User)).all()}

    weak_controls = get_weak_controls(session)
    overdue_actions = get_overdue_actions(session, today=today)
    overdue_reviews = [
        r for r in risks if r.next_review_date is not None and r.next_review_date < today
    ]
    appetite_statuses = compute_appetite_statuses(session, risks, today=today)

    status_counts: dict[str, int] = {}
    breach_risks = []
    for risk in risks:
        risk_status = appetite_statuses[risk.id]
        status_counts[risk_status] = status_counts.get(risk_status, 0) + 1
        if risk_status in ("outside_appetite", "material_breach"):
            breach_risks.append(
                {
                    "id": risk.id,
                    "risk_code": risk.risk_code,
                    "title": risk.title,
                    "residual_band": risk.residual_band.value if risk.residual_band else None,
                    "appetite_status": risk_status,
                }
            )

    return {
        "weak_controls_count": len(weak_controls),
        "weak_controls": [
            {
                "id": c.id,
                "control_code": c.control_code,
                "name": c.name,
                "operating_effectiveness": c.operating_effectiveness,
                "design_effectiveness": c.design_effectiveness,
            }
            for c in weak_controls
        ],
        "overdue_actions_count": len(overdue_actions),
        "overdue_actions": [
            {
                "id": a.id,
                "action_code": a.action_code,
                "title": a.title,
                "due_date": a.due_date.isoformat() if a.due_date else None,
                "owner_email": owner_emails.get(a.owner_id),
                "risk_id": a.risk_id,
            }
            for a in overdue_actions
        ],
        "overdue_reviews_count": len(overdue_reviews),
        "appetite_status_counts": status_counts,
        "breach_risks": breach_risks,
    }
