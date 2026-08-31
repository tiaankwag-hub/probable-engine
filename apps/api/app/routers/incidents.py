from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.app.deps import CurrentUser, get_db, require_permission
from packages.shared.audit import record_audit_event
from packages.shared.models.incident import Incident
from packages.shared.models.risk import Risk
from packages.shared.rbac import CREATE_INCIDENT, TRIGGER_INCIDENT_REVIEW, VIEW_RISKS
from packages.shared.schemas.incident import IncidentCreate, IncidentOut

router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])


def _generate_incident_code(session: Session) -> str:
    count = session.scalar(select(func.count()).select_from(Incident)) or 0
    candidate = f"INC-{count + 1:04d}"
    while session.scalar(select(Incident.id).where(Incident.incident_code == candidate)):
        count += 1
        candidate = f"INC-{count + 1:04d}"
    return candidate


@router.get("", response_model=list[IncidentOut])
def list_incidents(
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(VIEW_RISKS)),
):
    return db.scalars(select(Incident).order_by(Incident.incident_date.desc())).all()


@router.post("", response_model=IncidentOut, status_code=status.HTTP_201_CREATED)
def create_incident(
    payload: IncidentCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(CREATE_INCIDENT)),
):
    now = datetime.now(timezone.utc)
    incident = Incident(
        incident_code=_generate_incident_code(db),
        risk_id=payload.risk_id,
        control_id=payload.control_id,
        description=payload.description,
        incident_date=payload.incident_date,
        severity=payload.severity,
        suggests_likelihood_increase=payload.suggests_likelihood_increase,
        created_at=now,
        updated_at=now,
    )
    db.add(incident)
    db.flush()
    record_audit_event(
        db, actor=current_user.email, entity="incident", entity_id=incident.id, action="create",
        old_value=None,
        new_value={"description": incident.description, "severity": incident.severity.value},
        source="ui",
    )
    db.commit()
    db.refresh(incident)
    return incident


@router.post("/{incident_id}/trigger-review", response_model=IncidentOut)
def trigger_review(
    incident_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(TRIGGER_INCIDENT_REVIEW)),
):
    """Explicit, human-initiated action — an incident never silently moves
    a risk's next_review_date on its own (domain model principle: evidence
    a human confirms, not an automatic mutation)."""
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="incident not found")
    if incident.risk_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="incident is not linked to a risk"
        )
    risk = db.get(Risk, incident.risk_id)
    if risk is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="linked risk not found")

    now = datetime.now(timezone.utc)
    old_review_date = risk.next_review_date.isoformat() if risk.next_review_date else None
    risk.next_review_date = now.date()
    incident.review_triggered_at = now
    incident.updated_at = now
    db.flush()

    record_audit_event(
        db, actor=current_user.email, entity="risk", entity_id=risk.id, action="review_triggered",
        old_value={"next_review_date": old_review_date},
        new_value={"next_review_date": risk.next_review_date.isoformat(), "incident_id": str(incident.id)},
        source="ui",
    )
    db.commit()
    db.refresh(incident)
    return incident
