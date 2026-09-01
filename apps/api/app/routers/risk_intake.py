"""Guided Risk Intake API (post-Milestone-9 enhancement): a live,
turn-by-turn conversation for a non-expert user or executive to raise a
risk in plain language. Unlike every other AI capability in this codebase
(dispatched to `apps/worker` via `BackgroundJob`, see ADR 0005), each turn
here is a direct, synchronous call to the active `AIProvider` — a chat
needs to feel like a chat, not a poll loop. See
`packages/shared/risk_intake_service.py` for why a submitted session still
only ever creates a `draft` Risk through the normal `create_risk` path.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.deps import CurrentUser, get_db, require_permission
from packages.ai.factory import get_provider
from packages.shared.models.identity import User
from packages.shared.models.risk_intake import RiskIntakeSession
from packages.shared.rbac import REVIEW_RISK_INTAKE, SUBMIT_RISK_INTAKE, role_has_permission
from packages.shared.risk_intake_service import (
    IntakeSessionNotActiveError,
    finalize_session,
    start_session,
    submit_user_message,
)
from packages.shared.schemas.risk_intake import (
    IntakeMessageIn,
    IntakeSubmitOut,
    RiskIntakeSessionOut,
)

router = APIRouter(prefix="/api/v1/risk-intake", tags=["risk-intake"])


def _to_out(intake: RiskIntakeSession, *, initiated_by_email: str) -> RiskIntakeSessionOut:
    return RiskIntakeSessionOut(
        id=intake.id,
        status=intake.status,
        transcript=intake.transcript,
        draft_fields=intake.draft_fields,
        turn_count=intake.turn_count,
        model=intake.model,
        initiated_by_id=intake.initiated_by_id,
        initiated_by_email=initiated_by_email,
        resulting_risk_id=intake.resulting_risk_id,
        created_at=intake.created_at,
        updated_at=intake.updated_at,
    )


def _get_owned_session(
    db: Session, session_id: uuid.UUID, current_user: CurrentUser
) -> RiskIntakeSession:
    """A conversation is private to the person having it — reviewing every
    submitted session (REVIEW_RISK_INTAKE) does not grant the ability to
    chat or submit as someone else, only to read finished ones."""
    intake = db.get(RiskIntakeSession, session_id)
    if intake is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="risk intake session not found")
    if intake.initiated_by_id != current_user.user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not your risk intake session")
    return intake


@router.post("/sessions", response_model=RiskIntakeSessionOut, status_code=status.HTTP_201_CREATED)
def create_session(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(SUBMIT_RISK_INTAKE)),
):
    intake = start_session(db, user_id=current_user.user.id)
    db.commit()
    db.refresh(intake)
    return _to_out(intake, initiated_by_email=current_user.email)


@router.get("/sessions", response_model=list[RiskIntakeSessionOut])
def list_sessions(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(SUBMIT_RISK_INTAKE)),
):
    """Everyone with SUBMIT_RISK_INTAKE sees their own sessions; Risk
    Manager/Administrator (REVIEW_RISK_INTAKE) see every session, to triage
    which drafts need attention."""
    query = select(RiskIntakeSession).order_by(RiskIntakeSession.created_at.desc())
    if not any(role_has_permission(r, REVIEW_RISK_INTAKE) for r in current_user.roles):
        query = query.where(RiskIntakeSession.initiated_by_id == current_user.user.id)
    sessions = db.scalars(query).all()
    emails = {u.id: u.email for u in db.scalars(select(User)).all()}
    return [_to_out(s, initiated_by_email=emails.get(s.initiated_by_id, "unknown")) for s in sessions]


@router.get("/sessions/{session_id}", response_model=RiskIntakeSessionOut)
def get_session(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(SUBMIT_RISK_INTAKE)),
):
    intake = db.get(RiskIntakeSession, session_id)
    if intake is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="risk intake session not found")
    is_owner = intake.initiated_by_id == current_user.user.id
    can_review = any(role_has_permission(r, REVIEW_RISK_INTAKE) for r in current_user.roles)
    if not (is_owner or can_review):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="cannot view this risk intake session")
    owner = current_user.user if is_owner else db.get(User, intake.initiated_by_id)
    return _to_out(intake, initiated_by_email=owner.email if owner else "unknown")


@router.post("/sessions/{session_id}/messages", response_model=RiskIntakeSessionOut)
def post_message(
    session_id: uuid.UUID,
    payload: IntakeMessageIn,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(SUBMIT_RISK_INTAKE)),
):
    intake = _get_owned_session(db, session_id, current_user)
    if not payload.message.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="message must not be empty")
    try:
        submit_user_message(db, get_provider(), intake, message=payload.message)
    except IntakeSessionNotActiveError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    db.commit()
    db.refresh(intake)
    return _to_out(intake, initiated_by_email=current_user.email)


@router.post("/sessions/{session_id}/submit", response_model=IntakeSubmitOut)
def submit_session(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(SUBMIT_RISK_INTAKE)),
):
    intake = _get_owned_session(db, session_id, current_user)
    try:
        risk = finalize_session(
            db, intake, actor_id=current_user.user.id, actor_email=current_user.email
        )
    except IntakeSessionNotActiveError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    db.commit()
    return IntakeSubmitOut(risk_id=risk.id, risk_code=risk.risk_code)
