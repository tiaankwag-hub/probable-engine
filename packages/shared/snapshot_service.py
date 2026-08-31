"""Snapshot capture and period-over-period comparison (Milestone 4).

A snapshot freezes each risk's leadership-relevant fields at a point in
time (`SnapshotRisk.frozen_state`) so "What Changed?" can diff live data
against a specific prior period without replaying `risk_history` deltas.
Actions/controls are not snapshotted in this milestone — see the
Milestone 4 plan's deferred-scope note — so "changed" is currently scoped
to risk-level fields (status, band, score, owner, appetite).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.shared.audit import record_audit_event
from packages.shared.governance_service import compute_appetite_statuses
from packages.shared.models.risk import Risk, RiskBand, RiskStatus
from packages.shared.models.snapshot import Snapshot, SnapshotRisk

BAND_RANK = {RiskBand.LOW: 0, RiskBand.MODERATE: 1, RiskBand.HIGH: 2, RiskBand.EXTREME: 3}


def serialize_risk_for_snapshot(risk: Risk, appetite_status: str) -> dict[str, Any]:
    return {
        "risk_code": risk.risk_code,
        "title": risk.title,
        "status": risk.status.value,
        "category_id": str(risk.category_id) if risk.category_id else None,
        "owner_id": str(risk.owner_id) if risk.owner_id else None,
        "residual_score": risk.residual_score,
        "residual_band": risk.residual_band.value if risk.residual_band else None,
        "next_review_date": risk.next_review_date.isoformat() if risk.next_review_date else None,
        "appetite_status": appetite_status,
    }


def capture_snapshot(
    session: Session, *, label: str, period_end: date, actor_email: str
) -> Snapshot:
    """Freezes every risk's current state (including closed ones, so a
    later comparison can see the closure). Caller commits."""
    risks = session.scalars(select(Risk)).all()
    appetite_statuses = compute_appetite_statuses(session, risks, today=period_end)

    snapshot = Snapshot(label=label, period_end=period_end, created_at=datetime.now(timezone.utc))
    session.add(snapshot)
    session.flush()

    for risk in risks:
        session.add(
            SnapshotRisk(
                snapshot_id=snapshot.id,
                risk_id=risk.id,
                frozen_state=serialize_risk_for_snapshot(risk, appetite_statuses[risk.id]),
            )
        )

    record_audit_event(
        session,
        actor=actor_email,
        entity="snapshot",
        entity_id=snapshot.id,
        action="create",
        old_value=None,
        new_value={"label": label, "period_end": period_end.isoformat(), "risk_count": len(risks)},
        source="ui",
    )
    return snapshot


def compute_what_changed(session: Session, since_snapshot_id) -> dict[str, Any]:
    snapshot = session.get(Snapshot, since_snapshot_id)
    if snapshot is None:
        raise ValueError(f"snapshot not found: {since_snapshot_id}")

    prior_rows = session.scalars(
        select(SnapshotRisk).where(SnapshotRisk.snapshot_id == since_snapshot_id)
    ).all()
    prior_by_risk_id = {row.risk_id: row.frozen_state for row in prior_rows}

    current_risks = session.scalars(select(Risk)).all()
    current_by_id = {r.id: r for r in current_risks}
    appetite_statuses = compute_appetite_statuses(session, current_risks)

    new_risks = []
    closed_risks = []
    escalated_risks = []
    downgraded_risks = []
    owner_changes = []
    appetite_changes = []

    for risk in current_risks:
        prior = prior_by_risk_id.get(risk.id)
        if prior is None:
            new_risks.append({"id": risk.id, "risk_code": risk.risk_code, "title": risk.title})
            continue

        if prior["status"] != "closed" and risk.status == RiskStatus.CLOSED:
            closed_risks.append({"id": risk.id, "risk_code": risk.risk_code, "title": risk.title})

        prior_band = prior.get("residual_band")
        current_band = risk.residual_band.value if risk.residual_band else None
        if prior_band and current_band and prior_band != current_band:
            prior_rank = BAND_RANK[RiskBand(prior_band)]
            current_rank = BAND_RANK[RiskBand(current_band)]
            entry = {
                "id": risk.id, "risk_code": risk.risk_code, "title": risk.title,
                "from_band": prior_band, "to_band": current_band,
            }
            if current_rank > prior_rank:
                escalated_risks.append(entry)
            elif current_rank < prior_rank:
                downgraded_risks.append(entry)

        prior_owner = prior.get("owner_id")
        current_owner = str(risk.owner_id) if risk.owner_id else None
        if prior_owner != current_owner:
            owner_changes.append(
                {
                    "id": risk.id, "risk_code": risk.risk_code, "title": risk.title,
                    "from_owner_id": prior_owner, "to_owner_id": current_owner,
                }
            )

        prior_appetite = prior.get("appetite_status")
        current_appetite = appetite_statuses[risk.id]
        if prior_appetite != current_appetite:
            appetite_changes.append(
                {
                    "id": risk.id, "risk_code": risk.risk_code, "title": risk.title,
                    "from_status": prior_appetite, "to_status": current_appetite,
                }
            )

    return {
        "since_snapshot_id": since_snapshot_id,
        "since_label": snapshot.label,
        "since_period_end": snapshot.period_end.isoformat(),
        "new_risks": new_risks,
        "closed_risks": closed_risks,
        "escalated_risks": escalated_risks,
        "downgraded_risks": downgraded_risks,
        "owner_changes": owner_changes,
        "appetite_changes": appetite_changes,
    }


def compute_trend(session: Session) -> list[dict[str, Any]]:
    """One point per snapshot (chronological) plus a final 'current' point
    from live data, each with total/band counts, for the Trends page."""
    snapshots = session.scalars(select(Snapshot).order_by(Snapshot.period_end)).all()
    points = []

    for snapshot in snapshots:
        rows = session.scalars(
            select(SnapshotRisk).where(SnapshotRisk.snapshot_id == snapshot.id)
        ).all()
        counts = {"low": 0, "moderate": 0, "high": 0, "extreme": 0}
        total = 0
        for row in rows:
            if row.frozen_state.get("status") == "closed":
                continue
            band = row.frozen_state.get("residual_band")
            if band in counts:
                counts[band] += 1
            total += 1
        points.append(
            {"label": snapshot.label, "period_end": snapshot.period_end.isoformat(), "total_risks": total, **counts}
        )

    current_risks = session.scalars(select(Risk).where(Risk.status != RiskStatus.CLOSED)).all()
    current_counts = {"low": 0, "moderate": 0, "high": 0, "extreme": 0}
    for risk in current_risks:
        if risk.residual_band:
            current_counts[risk.residual_band.value] += 1
    points.append(
        {
            "label": "Current",
            "period_end": date.today().isoformat(),
            "total_risks": len(current_risks),
            **current_counts,
        }
    )
    return points
