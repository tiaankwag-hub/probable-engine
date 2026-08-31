"""Emerging Risk Radar API (Milestone 9, docs/architecture/02-domain-model.md).
Ingestion is dispatched through the JobQueue (ADR 0005) like every other
slow/AI-touching action in this system — `POST /ingest` isn't in the
original API design doc's abbreviated Emerging risks section, added here
the same way Milestone 8 added capabilities beyond its own original list
(see the Milestone 9 plan's "Deviations" section).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.deps import CurrentUser, get_db, require_permission
from packages.shared.emerging_risk_service import (
    CandidateAlreadyFinalizedError,
    InvalidCandidateTransitionError,
    link_candidate_to_existing_risk,
    transition_candidate,
)
from packages.shared.models.emerging_risk import (
    CandidateLifecycleStatus,
    EmergingCandidateSignal,
    EmergingRiskCandidate,
    EmergingSignal,
)
from packages.shared.models.jobs import BackgroundJob, JobStatus
from packages.shared.rbac import INGEST_EMERGING_SIGNALS, REVIEW_EMERGING_RISKS, VIEW_EMERGING_RISKS
from packages.shared.schemas.emerging_risk import (
    CandidateTransitionIn,
    EmergingRiskCandidateOut,
    EmergingSignalOut,
    IngestJobOut,
    LinkExistingRiskIn,
)

router = APIRouter(prefix="/api/v1/emerging-risks", tags=["emerging-risks"])


def _signals_for(db: Session, candidate_id: uuid.UUID) -> list[EmergingSignal]:
    return list(
        db.scalars(
            select(EmergingSignal)
            .join(EmergingCandidateSignal, EmergingCandidateSignal.signal_id == EmergingSignal.id)
            .where(EmergingCandidateSignal.candidate_id == candidate_id)
            .order_by(EmergingSignal.ingested_at)
        )
    )


def _to_out(db: Session, candidate: EmergingRiskCandidate) -> EmergingRiskCandidateOut:
    return EmergingRiskCandidateOut(
        id=candidate.id,
        title=candidate.title,
        summary=candidate.summary,
        category_id=candidate.category_id,
        category_name=candidate.category.name if candidate.category else None,
        relevance_assessment=candidate.relevance_assessment,
        model=candidate.model,
        lifecycle_status=candidate.lifecycle_status,
        matched_risk_id=candidate.matched_risk_id,
        created_risk_id=candidate.created_risk_id,
        reviewed_by_id=candidate.reviewed_by_id,
        reviewed_at=candidate.reviewed_at,
        created_at=candidate.created_at,
        updated_at=candidate.updated_at,
        signals=[EmergingSignalOut.model_validate(s) for s in _signals_for(db, candidate.id)],
    )


@router.post("/ingest", response_model=IngestJobOut, status_code=status.HTTP_202_ACCEPTED)
def ingest(
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(INGEST_EMERGING_SIGNALS)),
):
    now = datetime.now(timezone.utc)
    job = BackgroundJob(
        job_type="emerging_signal_ingest", payload={}, status=JobStatus.PENDING,
        created_at=now, updated_at=now,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return IngestJobOut(job_id=job.id)


@router.get("", response_model=list[EmergingRiskCandidateOut])
def list_candidates(
    lifecycle_status: CandidateLifecycleStatus | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(VIEW_EMERGING_RISKS)),
):
    query = select(EmergingRiskCandidate).order_by(EmergingRiskCandidate.created_at.desc())
    if lifecycle_status is not None:
        query = query.where(EmergingRiskCandidate.lifecycle_status == lifecycle_status)
    candidates = db.scalars(query).all()
    return [_to_out(db, c) for c in candidates]


@router.get("/{candidate_id}", response_model=EmergingRiskCandidateOut)
def get_candidate(
    candidate_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(VIEW_EMERGING_RISKS)),
):
    candidate = db.get(EmergingRiskCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="candidate not found")
    return _to_out(db, candidate)


@router.patch("/{candidate_id}", response_model=EmergingRiskCandidateOut)
def transition(
    candidate_id: uuid.UUID,
    payload: CandidateTransitionIn,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(REVIEW_EMERGING_RISKS)),
):
    candidate = db.get(EmergingRiskCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="candidate not found")
    try:
        transition_candidate(
            db, candidate,
            new_status=payload.lifecycle_status,
            reviewer_id=current_user.user.id,
            actor_email=current_user.email,
        )
    except CandidateAlreadyFinalizedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    except InvalidCandidateTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None
    db.commit()
    db.refresh(candidate)
    return _to_out(db, candidate)


@router.post("/{candidate_id}/link-existing-risk", response_model=EmergingRiskCandidateOut)
def link_existing_risk(
    candidate_id: uuid.UUID,
    payload: LinkExistingRiskIn,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(REVIEW_EMERGING_RISKS)),
):
    candidate = db.get(EmergingRiskCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="candidate not found")
    try:
        link_candidate_to_existing_risk(
            db, candidate,
            matched_risk_id=payload.risk_id,
            reviewer_id=current_user.user.id,
            actor_email=current_user.email,
        )
    except CandidateAlreadyFinalizedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None
    db.commit()
    db.refresh(candidate)
    return _to_out(db, candidate)
