"""AI orchestration (Milestone 8, ADR 0006): builds allow-listed prompt
contexts, calls the active `AIProvider`, persists `AIRun`/`AISuggestion`
rows, and applies an approved suggestion through the normal
`risk_service.update_risk` path so it produces its own `risk_history` and
`audit_events` rows, attributed to the approving human — never a direct
write from this module to `risks`.

Prompt contexts are built as explicit, hand-picked dicts (see
`build_executive_summary_context`/`build_risk_analysis_context`) — never
by passing an ORM object or a raw field dump into a provider. This is the
mitigation `docs/security/threat-model.md` calls for against sensitive
data leaking into a prompt or a log: a field can only reach an AI
provider if it's explicitly listed here.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.ai.provider import AIProvider, AIResponse
from packages.shared.dashboard_service import compute_executive_dashboard
from packages.shared.governance_service import NON_TERMINAL_ACTION_STATUSES
from packages.shared.models.action import Action
from packages.shared.models.ai import (
    AICapability,
    AIRun,
    AIRunStatus,
    AISuggestion,
    AISuggestionReviewStatus,
)
from packages.shared.models.incident import Incident
from packages.shared.models.risk import Risk
from packages.shared.risk_service import AssessmentInput, update_risk

PROMPT_VERSION = "v1"


class SuggestionAlreadyReviewedError(Exception):
    def __init__(self, suggestion_id: uuid.UUID):
        self.suggestion_id = suggestion_id
        super().__init__(f"suggestion {suggestion_id} has already been reviewed")


def build_executive_summary_context(session: Session) -> dict:
    dashboard = compute_executive_dashboard(session)
    return {
        "total_risks": dashboard["total_risks"],
        "extreme_count": dashboard["extreme_count"],
        "high_count": dashboard["high_count"],
        "moderate_count": dashboard["moderate_count"],
        "low_count": dashboard["low_count"],
        "weak_controls_count": dashboard["weak_controls_count"],
        "overdue_actions_count": dashboard["overdue_actions_count"],
        "risks_outside_appetite_count": dashboard["risks_outside_appetite_count"],
        "top_risk_titles": [r["title"] for r in dashboard["top_risks"][:5]],
    }


def build_risk_analysis_context(session: Session, risk: Risk) -> dict:
    """Allow-listed projection of one risk — only the fields listed here
    ever reach a prompt, regardless of what else `Risk` carries."""
    recent_incident_count = (
        session.scalar(select(func.count()).select_from(Incident).where(Incident.risk_id == risk.id))
        or 0
    )
    overdue_action_count = (
        session.scalar(
            select(func.count())
            .select_from(Action)
            .where(
                Action.risk_id == risk.id,
                Action.due_date < date.today(),
                Action.status.in_(NON_TERMINAL_ACTION_STATUSES),
            )
        )
        or 0
    )

    return {
        "title": risk.title,
        "statement": risk.statement or "(none provided)",
        "category": risk.category.name if risk.category else "Uncategorized",
        "likelihood": risk.likelihood,
        "control_effectiveness": risk.control_effectiveness,
        "residual_band": risk.residual_band.value if risk.residual_band else None,
        "recent_incident_count": recent_incident_count,
        "overdue_action_count": overdue_action_count,
    }


def create_pending_run(
    session: Session,
    *,
    capability: AICapability,
    requested_by_id: uuid.UUID,
    input_risk_ids: list[uuid.UUID],
    sources: dict,
) -> AIRun:
    """Creates the `AIRun` row a background job will fill in — called from
    the API router before enqueuing, mirroring `ReportRun`/`SimulationRun`'s
    pending-then-processed shape so the frontend has an id to poll
    immediately."""
    now = datetime.now(timezone.utc)
    run = AIRun(
        capability=capability,
        prompt_version=PROMPT_VERSION,
        requested_by_id=requested_by_id,
        input_risk_ids=[str(i) for i in input_risk_ids],
        sources=sources,
        status=AIRunStatus.PENDING,
        created_at=now,
        updated_at=now,
    )
    session.add(run)
    session.flush()
    return run


def _apply_response(run: AIRun, response: AIResponse) -> None:
    now = datetime.now(timezone.utc)
    run.model = response.model
    run.raw_response = response.text
    run.latency_ms = response.latency_ms
    run.status = AIRunStatus.SUCCEEDED
    run.updated_at = now
    run.completed_at = now


def execute_executive_summary(session: Session, provider: AIProvider, run: AIRun) -> None:
    """Fills in a pending executive-summary `AIRun` in place. Caller
    (the worker job) commits."""
    context = build_executive_summary_context(session)
    response = provider.generate_executive_summary(context)
    _apply_response(run, response)


def execute_risk_analysis(session: Session, provider: AIProvider, run: AIRun, *, risk: Risk) -> None:
    """Fills in a pending risk-analysis `AIRun` in place and persists any
    suggestions the provider drafted, each `pending` review. Caller (the
    worker job) commits."""
    context = build_risk_analysis_context(session, risk)
    response = provider.analyze_risk(context)
    _apply_response(run, response)

    now = datetime.now(timezone.utc)
    for draft in response.suggestions:
        session.add(
            AISuggestion(
                run_id=run.id,
                risk_id=risk.id,
                suggestion_type=draft.suggestion_type,
                summary=draft.summary,
                rationale=draft.rationale,
                proposed_changes=draft.proposed_changes,
                human_review_status=AISuggestionReviewStatus.PENDING,
                created_at=now,
            )
        )


def approve_suggestion(
    session: Session,
    suggestion: AISuggestion,
    *,
    reviewer_id: uuid.UUID,
    actor_email: str,
) -> Risk:
    """Applies `proposed_changes` through the normal, audited risk-update
    path — the only code path in this codebase that can change a risk
    from an AI suggestion, per ADR 0006. Fields the suggestion doesn't
    mention keep the risk's current values, read from its latest
    assessment rather than assumed."""
    if suggestion.human_review_status != AISuggestionReviewStatus.PENDING:
        raise SuggestionAlreadyReviewedError(suggestion.id)

    risk = session.get(Risk, suggestion.risk_id)
    latest_assessment = risk.assessments[0] if risk.assessments else None
    current_impact_by_dimension = (
        {score.dimension.value: score.score for score in latest_assessment.impact_scores}
        if latest_assessment
        else {}
    )

    changes = suggestion.proposed_changes
    assessment_input = AssessmentInput(
        likelihood=changes.get("likelihood", risk.likelihood),
        impact_financial=changes.get("impact_financial", current_impact_by_dimension.get("financial", 3)),
        impact_customer_service=changes.get(
            "impact_customer_service", current_impact_by_dimension.get("customer_service", 3)
        ),
        impact_operational_delivery=changes.get(
            "impact_operational_delivery", current_impact_by_dimension.get("operational_delivery", 3)
        ),
        impact_legal_regulatory=changes.get(
            "impact_legal_regulatory", current_impact_by_dimension.get("legal_regulatory", 3)
        ),
        impact_reputation=changes.get("impact_reputation", current_impact_by_dimension.get("reputation", 3)),
        impact_health_safety=changes.get(
            "impact_health_safety", current_impact_by_dimension.get("health_safety", 3)
        ),
        control_effectiveness=changes.get("control_effectiveness", risk.control_effectiveness),
    )

    updated_risk = update_risk(
        session,
        risk=risk,
        expected_version=risk.version,
        field_updates={},
        assessment_input=assessment_input,
        actor_email=actor_email,
        actor_id=reviewer_id,
        source="ai-approved",
    )

    suggestion.human_review_status = AISuggestionReviewStatus.APPROVED
    suggestion.reviewed_by_id = reviewer_id
    suggestion.reviewed_at = datetime.now(timezone.utc)
    return updated_risk


def reject_suggestion(session: Session, suggestion: AISuggestion, *, reviewer_id: uuid.UUID) -> None:
    if suggestion.human_review_status != AISuggestionReviewStatus.PENDING:
        raise SuggestionAlreadyReviewedError(suggestion.id)

    suggestion.human_review_status = AISuggestionReviewStatus.REJECTED
    suggestion.reviewed_by_id = reviewer_id
    suggestion.reviewed_at = datetime.now(timezone.utc)
