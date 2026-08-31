"""AI provider integration API (Milestone 8, ADR 0006): request an
executive summary or a single risk's AI analysis (dispatched to
apps/worker via the JobQueue, same async pattern as reports/simulations
— a live LLM call is exactly the kind of request-blocking latency that
pattern exists for), poll for results, and review any suggestion the
analysis produced. Approving a suggestion is the *only* path from an AI
output to an actual change on a risk — see `packages/shared/ai_service.py`.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.deps import CurrentUser, get_current_user, get_db, require_permission
from packages.shared.ai_service import (
    SuggestionAlreadyReviewedError,
    approve_suggestion,
    create_pending_run,
    reject_suggestion,
)
from packages.shared.models.ai import AICapability, AIRun, AIRunStatus, AISuggestion, AISuggestionReviewStatus
from packages.shared.models.jobs import BackgroundJob, JobStatus
from packages.shared.models.risk import Risk
from packages.shared.rbac import (
    APPROVE_AI_SUGGESTIONS,
    REQUEST_ANY_AI_ANALYSIS,
    REQUEST_EXECUTIVE_SUMMARY,
    REQUEST_OWN_AI_ANALYSIS,
    role_has_permission,
)
from packages.shared.schemas.ai import AIRunOut, AISuggestionOut, RiskAnalysisRequest

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])

_AI_VISIBILITY_PERMISSIONS = (
    REQUEST_OWN_AI_ANALYSIS,
    REQUEST_ANY_AI_ANALYSIS,
    REQUEST_EXECUTIVE_SUMMARY,
    APPROVE_AI_SUGGESTIONS,
)


def _can_analyze_risk(current_user: CurrentUser, risk: Risk) -> bool:
    if any(role_has_permission(r, REQUEST_ANY_AI_ANALYSIS) for r in current_user.roles):
        return True
    if any(role_has_permission(r, REQUEST_OWN_AI_ANALYSIS) for r in current_user.roles):
        return risk.owner_id == current_user.user.id
    return False


def _can_view_ai(current_user: CurrentUser) -> bool:
    return any(
        role_has_permission(r, permission)
        for r in current_user.roles
        for permission in _AI_VISIBILITY_PERMISSIONS
    )


def _to_suggestion_out(suggestion: AISuggestion) -> AISuggestionOut:
    return AISuggestionOut(
        id=suggestion.id,
        run_id=suggestion.run_id,
        risk_id=suggestion.risk_id,
        suggestion_type=suggestion.suggestion_type,
        summary=suggestion.summary,
        rationale=suggestion.rationale,
        proposed_changes=suggestion.proposed_changes,
        human_review_status=suggestion.human_review_status,
        reviewed_by_id=suggestion.reviewed_by_id,
        reviewed_at=suggestion.reviewed_at,
        created_at=suggestion.created_at,
    )


def _to_run_out(run: AIRun, suggestions: list[AISuggestion]) -> AIRunOut:
    return AIRunOut(
        id=run.id,
        capability=run.capability,
        model=run.model,
        prompt_version=run.prompt_version,
        status=run.status,
        narrative=run.raw_response,
        latency_ms=run.latency_ms,
        error=run.error,
        created_at=run.created_at,
        completed_at=run.completed_at,
        suggestions=[_to_suggestion_out(s) for s in suggestions],
    )


def _enqueue(db: Session, run: AIRun, *, extra_payload: dict | None = None) -> None:
    now = datetime.now(timezone.utc)
    payload = {"run_id": str(run.id)}
    if extra_payload:
        payload.update(extra_payload)
    db.add(
        BackgroundJob(
            job_type="ai_run", payload=payload, status=JobStatus.PENDING, created_at=now, updated_at=now
        )
    )


@router.post("/executive-summary", response_model=AIRunOut, status_code=status.HTTP_202_ACCEPTED)
def request_executive_summary(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(REQUEST_EXECUTIVE_SUMMARY)),
):
    run = create_pending_run(
        db,
        capability=AICapability.EXECUTIVE_SUMMARY,
        requested_by_id=current_user.user.id,
        input_risk_ids=[],
        sources={"kind": "executive_dashboard_snapshot"},
    )
    _enqueue(db, run)
    db.commit()
    db.refresh(run)
    return _to_run_out(run, [])


@router.post("/risk-analysis", response_model=AIRunOut, status_code=status.HTTP_202_ACCEPTED)
def request_risk_analysis(
    payload: RiskAnalysisRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    risk = db.get(Risk, payload.risk_id)
    if risk is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="risk not found")
    if not _can_analyze_risk(current_user, risk):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="cannot analyze this risk")

    run = create_pending_run(
        db,
        capability=AICapability.RISK_ANALYSIS,
        requested_by_id=current_user.user.id,
        input_risk_ids=[risk.id],
        sources={"kind": "risk_snapshot", "risk_id": str(risk.id)},
    )
    _enqueue(db, run, extra_payload={"risk_id": str(risk.id)})
    db.commit()
    db.refresh(run)
    return _to_run_out(run, [])


@router.get("/runs/{run_id}", response_model=AIRunOut)
def get_run(
    run_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    if not _can_view_ai(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="missing AI visibility permission")
    run = db.get(AIRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI run not found")
    suggestions = db.scalars(select(AISuggestion).where(AISuggestion.run_id == run_id)).all()
    return _to_run_out(run, suggestions)


@router.get("/suggestions", response_model=list[AISuggestionOut])
def list_suggestions(
    status_filter: AISuggestionReviewStatus | None = Query(default=None, alias="status"),
    risk_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Scoped to one risk (`risk_id` set): visible to whoever could have
    requested that risk's analysis (its owner, or any Risk
    Manager/Administrator) — a Risk Owner should see what was suggested
    even though only Risk Manager/Administrator can approve it.
    Unscoped (the reviewer queue): restricted to `APPROVE_AI_SUGGESTIONS`
    roles only, matching the brief's matrix exactly."""
    if risk_id is not None:
        risk = db.get(Risk, risk_id)
        if risk is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="risk not found")
        if not _can_analyze_risk(current_user, risk):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="cannot view suggestions for this risk")
    elif not any(role_has_permission(r, APPROVE_AI_SUGGESTIONS) for r in current_user.roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="missing required permission: approve_ai_suggestions",
        )

    query = select(AISuggestion).order_by(AISuggestion.created_at.desc())
    if status_filter is not None:
        query = query.where(AISuggestion.human_review_status == status_filter)
    if risk_id is not None:
        query = query.where(AISuggestion.risk_id == risk_id)
    suggestions = db.scalars(query).all()
    return [_to_suggestion_out(s) for s in suggestions]


@router.post("/suggestions/{suggestion_id}/approve", response_model=AISuggestionOut)
def approve(
    suggestion_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(APPROVE_AI_SUGGESTIONS)),
):
    suggestion = db.get(AISuggestion, suggestion_id)
    if suggestion is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="suggestion not found")
    try:
        approve_suggestion(
            db, suggestion, reviewer_id=current_user.user.id, actor_email=current_user.email
        )
    except SuggestionAlreadyReviewedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    db.commit()
    db.refresh(suggestion)
    return _to_suggestion_out(suggestion)


@router.post("/suggestions/{suggestion_id}/reject", response_model=AISuggestionOut)
def reject(
    suggestion_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(APPROVE_AI_SUGGESTIONS)),
):
    suggestion = db.get(AISuggestion, suggestion_id)
    if suggestion is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="suggestion not found")
    try:
        reject_suggestion(db, suggestion, reviewer_id=current_user.user.id)
    except SuggestionAlreadyReviewedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    db.commit()
    db.refresh(suggestion)
    return _to_suggestion_out(suggestion)
