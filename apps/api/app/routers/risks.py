from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.app.deps import CurrentUser, get_current_user, get_db, require_permission
from packages.shared.appetite_repo import compute_appetite_status_for_risk
from packages.shared.audit import record_audit_event
from packages.shared.models.action import Action
from packages.shared.models.control import Control, RiskControl
from packages.shared.models.incident import Incident
from packages.shared.models.issue import Issue
from packages.shared.models.risk import Risk, RiskDecision, RiskHistory, RiskStatus
from packages.shared.rbac import (
    CREATE_OWN_RISK,
    EDIT_ANY_RISK,
    EDIT_OWN_RISK,
    VIEW_RISKS,
    role_has_permission,
)
from packages.shared.risk_service import (
    AcceptanceRationaleRequiredError,
    AssessmentInput,
    OptimisticConcurrencyError,
    RiskFields,
    create_risk,
    update_risk,
)
from packages.shared.schemas.action import ActionOut
from packages.shared.schemas.control import ControlOut, LinkControlIn
from packages.shared.schemas.incident import IncidentOut
from packages.shared.schemas.issue import IssueOut
from packages.shared.schemas.risk import (
    RiskAssessmentOut,
    RiskCreate,
    RiskDetailOut,
    RiskHistoryOut,
    RiskOut,
    RiskUpdate,
)

router = APIRouter(prefix="/api/v1/risks", tags=["risks"])


def _can_edit(current_user: CurrentUser, risk: Risk) -> bool:
    if any(role_has_permission(r, EDIT_ANY_RISK) for r in current_user.roles):
        return True
    if any(role_has_permission(r, EDIT_OWN_RISK) for r in current_user.roles):
        return risk.owner_id == current_user.user.id
    return False


@router.get("", response_model=list[RiskOut])
def list_risks(
    response: Response,
    status_filter: RiskStatus | None = Query(default=None, alias="status"),
    category_id: uuid.UUID | None = None,
    owner_id: uuid.UUID | None = None,
    q: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(VIEW_RISKS)),
):
    query = select(Risk)
    if status_filter is not None:
        query = query.where(Risk.status == status_filter)
    if category_id is not None:
        query = query.where(Risk.category_id == category_id)
    if owner_id is not None:
        query = query.where(Risk.owner_id == owner_id)
    if q:
        like = f"%{q}%"
        query = query.where((Risk.title.ilike(like)) | (Risk.risk_code.ilike(like)))

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    response.headers["X-Total-Count"] = str(total)

    rows = db.scalars(
        query.order_by(Risk.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return rows


@router.post("", response_model=RiskOut, status_code=status.HTTP_201_CREATED)
def create_risk_endpoint(
    payload: RiskCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(CREATE_OWN_RISK)),
):
    fields = RiskFields(
        title=payload.title,
        statement=payload.statement,
        cause=payload.cause,
        event=payload.event,
        impact=payload.impact,
        category_id=payload.category_id,
        business_process=payload.business_process,
        department=payload.department,
        owner_id=payload.owner_id or current_user.user.id,
        accountable_executive_id=payload.accountable_executive_id,
        status=payload.status.value,
        decision=payload.decision.value,
        acceptance_rationale=payload.acceptance_rationale,
        raised_date=payload.raised_date,
        next_review_date=payload.next_review_date,
        velocity=payload.velocity,
        confidence=payload.confidence,
        treatment_summary=payload.treatment_summary,
        latest_update=payload.latest_update,
    )
    assessment = AssessmentInput(
        likelihood=payload.assessment.likelihood,
        impact_financial=payload.assessment.impact_scores.financial,
        impact_customer_service=payload.assessment.impact_scores.customer_service,
        impact_operational_delivery=payload.assessment.impact_scores.operational_delivery,
        impact_legal_regulatory=payload.assessment.impact_scores.legal_regulatory,
        impact_reputation=payload.assessment.impact_scores.reputation,
        impact_health_safety=payload.assessment.impact_scores.health_safety,
        control_effectiveness=payload.assessment.control_effectiveness,
    )
    try:
        risk = create_risk(
            db,
            fields=fields,
            assessment_input=assessment,
            actor_email=current_user.email,
            actor_id=current_user.user.id,
            source="ui",
            risk_code=payload.risk_code,
        )
        db.commit()
    except AcceptanceRationaleRequiredError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="acceptance_rationale is required when decision is 'accept'",
        ) from None
    db.refresh(risk)
    return risk


@router.get("/{risk_id}", response_model=RiskDetailOut)
def get_risk(
    risk_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(VIEW_RISKS)),
):
    risk = db.get(Risk, risk_id)
    if risk is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="risk not found")
    appetite_status = compute_appetite_status_for_risk(db, risk)
    return RiskDetailOut(**RiskOut.model_validate(risk).model_dump(), appetite_status=appetite_status)


@router.patch("/{risk_id}", response_model=RiskOut)
def update_risk_endpoint(
    risk_id: uuid.UUID,
    payload: RiskUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    risk = db.get(Risk, risk_id)
    if risk is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="risk not found")
    if not _can_edit(current_user, risk):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="cannot edit this risk")

    field_updates = payload.model_dump(
        exclude={"version", "assessment"}, exclude_unset=True
    )
    if "status" in field_updates and field_updates["status"] is not None:
        field_updates["status"] = RiskStatus(field_updates["status"])
    if "decision" in field_updates and field_updates["decision"] is not None:
        field_updates["decision"] = RiskDecision(field_updates["decision"])

    assessment_input = None
    if payload.assessment is not None:
        assessment_input = AssessmentInput(
            likelihood=payload.assessment.likelihood,
            impact_financial=payload.assessment.impact_scores.financial,
            impact_customer_service=payload.assessment.impact_scores.customer_service,
            impact_operational_delivery=payload.assessment.impact_scores.operational_delivery,
            impact_legal_regulatory=payload.assessment.impact_scores.legal_regulatory,
            impact_reputation=payload.assessment.impact_scores.reputation,
            impact_health_safety=payload.assessment.impact_scores.health_safety,
            control_effectiveness=payload.assessment.control_effectiveness,
        )

    try:
        risk = update_risk(
            db,
            risk=risk,
            expected_version=payload.version,
            field_updates=field_updates,
            assessment_input=assessment_input,
            actor_email=current_user.email,
            actor_id=current_user.user.id,
            source="ui",
        )
        db.commit()
    except OptimisticConcurrencyError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    except AcceptanceRationaleRequiredError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="acceptance_rationale is required when decision is 'accept'",
        ) from None
    db.refresh(risk)
    return risk


@router.get("/{risk_id}/history", response_model=list[RiskHistoryOut])
def get_risk_history(
    risk_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(VIEW_RISKS)),
):
    risk = db.get(Risk, risk_id)
    if risk is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="risk not found")
    return db.scalars(
        select(RiskHistory).where(RiskHistory.risk_id == risk_id).order_by(
            RiskHistory.version.desc()
        )
    ).all()


@router.get("/{risk_id}/assessments", response_model=list[RiskAssessmentOut])
def get_risk_assessments(
    risk_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(VIEW_RISKS)),
):
    risk = db.get(Risk, risk_id)
    if risk is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="risk not found")
    return risk.assessments


@router.get("/{risk_id}/controls", response_model=list[ControlOut])
def get_risk_controls(
    risk_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(VIEW_RISKS)),
):
    risk = db.get(Risk, risk_id)
    if risk is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="risk not found")
    return db.scalars(
        select(Control).join(RiskControl, RiskControl.control_id == Control.id).where(
            RiskControl.risk_id == risk_id
        )
    ).all()


@router.post("/{risk_id}/controls", response_model=ControlOut, status_code=status.HTTP_201_CREATED)
def link_control_to_risk(
    risk_id: uuid.UUID,
    payload: LinkControlIn,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    risk = db.get(Risk, risk_id)
    if risk is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="risk not found")
    if not _can_edit(current_user, risk):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="cannot edit this risk")
    control = db.get(Control, payload.control_id)
    if control is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="control not found")

    existing = db.scalars(
        select(RiskControl).where(
            RiskControl.risk_id == risk_id, RiskControl.control_id == payload.control_id
        )
    ).first()
    if existing is None:
        db.add(RiskControl(risk_id=risk_id, control_id=payload.control_id))
        record_audit_event(
            db, actor=current_user.email, entity="risk", entity_id=risk_id, action="link_control",
            old_value=None, new_value={"control_id": str(payload.control_id)}, source="ui",
        )
        db.commit()
    return control


@router.delete("/{risk_id}/controls/{control_id}", status_code=status.HTTP_204_NO_CONTENT)
def unlink_control_from_risk(
    risk_id: uuid.UUID,
    control_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    risk = db.get(Risk, risk_id)
    if risk is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="risk not found")
    if not _can_edit(current_user, risk):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="cannot edit this risk")

    db.query(RiskControl).filter(
        RiskControl.risk_id == risk_id, RiskControl.control_id == control_id
    ).delete()
    record_audit_event(
        db, actor=current_user.email, entity="risk", entity_id=risk_id, action="unlink_control",
        old_value={"control_id": str(control_id)}, new_value=None, source="ui",
    )
    db.commit()


@router.get("/{risk_id}/actions", response_model=list[ActionOut])
def get_risk_actions(
    risk_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(VIEW_RISKS)),
):
    risk = db.get(Risk, risk_id)
    if risk is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="risk not found")
    return db.scalars(
        select(Action).where(Action.risk_id == risk_id).order_by(Action.due_date)
    ).all()


@router.get("/{risk_id}/issues", response_model=list[IssueOut])
def get_risk_issues(
    risk_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(VIEW_RISKS)),
):
    risk = db.get(Risk, risk_id)
    if risk is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="risk not found")
    return db.scalars(
        select(Issue).where(Issue.risk_id == risk_id).order_by(Issue.created_at.desc())
    ).all()


@router.get("/{risk_id}/incidents", response_model=list[IncidentOut])
def get_risk_incidents(
    risk_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(VIEW_RISKS)),
):
    risk = db.get(Risk, risk_id)
    if risk is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="risk not found")
    return db.scalars(
        select(Incident).where(Incident.risk_id == risk_id).order_by(Incident.incident_date.desc())
    ).all()
