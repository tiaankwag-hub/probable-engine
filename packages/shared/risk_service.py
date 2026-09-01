"""Shared risk create/update logic used by both apps/api (interactive CRUD)
and apps/worker (import commit), so the two never diverge on how a risk is
scored, versioned, and audited (ADR 0001, ADR 0012).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.risk_engine.scoring import ImpactScores, score_risk
from packages.shared.audit import record_audit_event
from packages.shared.models.risk import (
    Risk,
    RiskAssessment,
    RiskBand,
    RiskCategory,
    RiskDecision,
    RiskHistory,
    RiskImpactScore,
    RiskStatus,
)
from packages.shared.scoring_config_repo import get_active_scoring_config


def find_category_by_name(session: Session, category_name: str | None) -> uuid.UUID | None:
    """Case-insensitive exact match against the real taxonomy — used
    wherever an AI capability proposes a category by name rather than id.
    Never trusted as-is; falls back to None (Uncategorized) on no match."""
    if not category_name:
        return None
    category = session.scalars(
        select(RiskCategory).where(func.lower(RiskCategory.name) == category_name.strip().lower())
    ).first()
    return category.id if category else None


class OptimisticConcurrencyError(Exception):
    pass


class AcceptanceRationaleRequiredError(Exception):
    pass


@dataclass
class AssessmentInput:
    likelihood: int
    impact_financial: int
    impact_customer_service: int
    impact_operational_delivery: int
    impact_legal_regulatory: int
    impact_reputation: int
    impact_health_safety: int
    control_effectiveness: int | None = None


@dataclass
class RiskFields:
    title: str
    statement: str | None = None
    cause: str | None = None
    event: str | None = None
    impact: str | None = None
    category_id: uuid.UUID | None = None
    business_process: str | None = None
    department: str | None = None
    owner_id: uuid.UUID | None = None
    accountable_executive_id: uuid.UUID | None = None
    status: str = "draft"
    decision: str = "pending"
    acceptance_rationale: str | None = None
    raised_date: date | None = None
    next_review_date: date | None = None
    velocity: str | None = None
    confidence: str | None = None
    treatment_summary: str | None = None
    latest_update: str | None = None


def generate_risk_code(session: Session) -> str:
    count = session.scalar(select(func.count()).select_from(Risk)) or 0
    candidate = f"RSK-{count + 1:04d}"
    while session.scalar(select(Risk.id).where(Risk.risk_code == candidate)):
        count += 1
        candidate = f"RSK-{count + 1:04d}"
    return candidate


def serialize_risk_state(risk: Risk) -> dict:
    return {
        "risk_code": risk.risk_code,
        "title": risk.title,
        "statement": risk.statement,
        "cause": risk.cause,
        "event": risk.event,
        "impact": risk.impact,
        "category_id": str(risk.category_id) if risk.category_id else None,
        "business_process": risk.business_process,
        "department": risk.department,
        "owner_id": str(risk.owner_id) if risk.owner_id else None,
        "accountable_executive_id": (
            str(risk.accountable_executive_id) if risk.accountable_executive_id else None
        ),
        "status": risk.status.value,
        "decision": risk.decision.value,
        "acceptance_rationale": risk.acceptance_rationale,
        "raised_date": risk.raised_date.isoformat() if risk.raised_date else None,
        "next_review_date": risk.next_review_date.isoformat() if risk.next_review_date else None,
        "likelihood": risk.likelihood,
        "overall_impact": risk.overall_impact,
        "inherent_score": risk.inherent_score,
        "inherent_band": risk.inherent_band.value if risk.inherent_band else None,
        "control_effectiveness": risk.control_effectiveness,
        "residual_score": risk.residual_score,
        "residual_band": risk.residual_band.value if risk.residual_band else None,
        "velocity": risk.velocity,
        "confidence": risk.confidence,
        "treatment_summary": risk.treatment_summary,
        "latest_update": risk.latest_update,
        "version": risk.version,
    }


def _apply_assessment(
    session: Session, risk: Risk, assessment_input: AssessmentInput, actor_id: uuid.UUID | None
) -> None:
    config = get_active_scoring_config(session)
    scores = ImpactScores(
        financial=assessment_input.impact_financial,
        customer_service=assessment_input.impact_customer_service,
        operational_delivery=assessment_input.impact_operational_delivery,
        legal_regulatory=assessment_input.impact_legal_regulatory,
        reputation=assessment_input.impact_reputation,
        health_safety=assessment_input.impact_health_safety,
    )
    result = score_risk(
        scores=scores,
        likelihood=assessment_input.likelihood,
        control_effectiveness=assessment_input.control_effectiveness,
        config=config,
    )

    inherent_band = RiskBand(result.inherent_band)
    residual_band = RiskBand(result.residual_band) if result.residual_band else None

    now = datetime.now(timezone.utc)
    assessment = RiskAssessment(
        risk_id=risk.id,
        likelihood=assessment_input.likelihood,
        overall_impact=result.overall_impact,
        inherent_score=result.inherent_score,
        inherent_band=inherent_band,
        control_effectiveness=result.control_effectiveness,
        residual_score=result.residual_score,
        residual_band=residual_band,
        scoring_config_version=result.scoring_config_version,
        assessed_by=actor_id,
        assessed_at=now,
    )
    session.add(assessment)
    session.flush()

    for dimension, value in scores.as_dict().items():
        session.add(
            RiskImpactScore(assessment_id=assessment.id, dimension=dimension, score=value)
        )

    risk.likelihood = assessment_input.likelihood
    risk.overall_impact = result.overall_impact
    risk.inherent_score = result.inherent_score
    risk.inherent_band = inherent_band
    risk.control_effectiveness = result.control_effectiveness
    risk.residual_score = result.residual_score
    risk.residual_band = residual_band


def create_risk(
    session: Session,
    *,
    fields: RiskFields,
    assessment_input: AssessmentInput,
    actor_email: str,
    actor_id: uuid.UUID | None,
    source: str,
    risk_code: str | None = None,
) -> Risk:
    if fields.decision == "accept" and not fields.acceptance_rationale:
        raise AcceptanceRationaleRequiredError()

    risk = Risk(
        risk_code=risk_code or generate_risk_code(session),
        title=fields.title,
        statement=fields.statement,
        cause=fields.cause,
        event=fields.event,
        impact=fields.impact,
        category_id=fields.category_id,
        business_process=fields.business_process,
        department=fields.department,
        owner_id=fields.owner_id,
        accountable_executive_id=fields.accountable_executive_id,
        status=RiskStatus(fields.status),
        decision=RiskDecision(fields.decision),
        acceptance_rationale=fields.acceptance_rationale,
        raised_date=fields.raised_date,
        next_review_date=fields.next_review_date,
        velocity=fields.velocity,
        confidence=fields.confidence,
        treatment_summary=fields.treatment_summary,
        latest_update=fields.latest_update,
        version=1,
    )
    session.add(risk)
    session.flush()

    _apply_assessment(session, risk, assessment_input, actor_id)
    session.flush()

    session.add(
        RiskHistory(
            risk_id=risk.id,
            version=risk.version,
            field_state=serialize_risk_state(risk),
            recorded_at=datetime.now(timezone.utc),
            actor=actor_email,
        )
    )
    record_audit_event(
        session,
        actor=actor_email,
        entity="risk",
        entity_id=risk.id,
        action="create",
        old_value=None,
        new_value=serialize_risk_state(risk),
        source=source,
    )
    return risk


def update_risk(
    session: Session,
    *,
    risk: Risk,
    expected_version: int,
    field_updates: dict,
    assessment_input: AssessmentInput | None,
    actor_email: str,
    actor_id: uuid.UUID | None,
    source: str,
) -> Risk:
    if risk.version != expected_version:
        raise OptimisticConcurrencyError(
            f"expected version {expected_version}, current version is {risk.version}"
        )

    old_state = serialize_risk_state(risk)

    decision = field_updates.get("decision", risk.decision)
    acceptance_rationale = field_updates.get("acceptance_rationale", risk.acceptance_rationale)
    decision_value = decision.value if hasattr(decision, "value") else decision
    if decision_value == "accept" and not acceptance_rationale:
        raise AcceptanceRationaleRequiredError()

    for field_name, value in field_updates.items():
        setattr(risk, field_name, value)

    if assessment_input is not None:
        _apply_assessment(session, risk, assessment_input, actor_id)

    risk.version += 1
    session.flush()

    new_state = serialize_risk_state(risk)
    session.add(
        RiskHistory(
            risk_id=risk.id,
            version=risk.version,
            field_state=new_state,
            recorded_at=datetime.now(timezone.utc),
            actor=actor_email,
        )
    )
    record_audit_event(
        session,
        actor=actor_email,
        entity="risk",
        entity_id=risk.id,
        action="update",
        old_value=old_state,
        new_value=new_state,
        source=source,
    )
    return risk
