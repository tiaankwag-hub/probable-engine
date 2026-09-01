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
from packages.shared.audit import record_audit_event
from packages.shared.control_service import ControlFields, create_control
from packages.shared.dashboard_service import compute_executive_dashboard
from packages.shared.governance_service import NON_TERMINAL_ACTION_STATUSES, compute_governance_health
from packages.shared.models.action import Action
from packages.shared.models.ai import (
    AICapability,
    AIRun,
    AIRunStatus,
    AISuggestion,
    AISuggestionReviewStatus,
)
from packages.shared.models.control import Control, ControlAutomation, ControlType, RiskControl
from packages.shared.models.emerging_risk import CandidateLifecycleStatus, EmergingRiskCandidate
from packages.shared.models.incident import Incident
from packages.shared.models.risk import Risk, RiskCategory
from packages.shared.risk_service import AssessmentInput, RiskFields, create_risk, update_risk
from packages.shared.snapshot_service import compute_trend

PROMPT_VERSION = "v1"


class SuggestionAlreadyReviewedError(Exception):
    def __init__(self, suggestion_id: uuid.UUID):
        self.suggestion_id = suggestion_id
        super().__init__(f"suggestion {suggestion_id} has already been reviewed")


def _format_top_risks_block(top_risks: list[dict]) -> str:
    if not top_risks:
        return "(no risks scored yet)"
    lines = []
    for r in top_risks[:5]:
        band = (r["residual_band"] or "unscored").capitalize()
        category = r["category_name"] or "Uncategorized"
        score = f"{r['residual_score']:.2f}" if r["residual_score"] is not None else "n/a"
        lines.append(f"- {r['risk_code']} {r['title']} — {category}, residual {score} ({band})")
    return "\n".join(lines)


def _format_category_exposure_block(category_exposure: list[dict]) -> str:
    if not category_exposure:
        return "(no risks registered)"
    parts = []
    for c in category_exposure[:6]:
        avg = f"{c['avg_residual_score']:.1f}" if c["avg_residual_score"] is not None else "n/a"
        parts.append(f"{c['category_name']} ({c['risk_count']} risk(s), avg residual {avg})")
    return "; ".join(parts)


def _format_appetite_summary(status_counts: dict[str, int]) -> str:
    within = status_counts.get("within_appetite", 0)
    approaching = status_counts.get("approaching_tolerance", 0)
    outside = status_counts.get("outside_appetite", 0)
    breach = status_counts.get("material_breach", 0)
    not_configured = status_counts.get("not_configured", 0)
    summary = (
        f"{within} risk(s) within appetite, {approaching} approaching tolerance, "
        f"{outside} outside appetite, and {breach} in material breach"
    )
    if not_configured:
        summary += f" ({not_configured} have no appetite/tolerance configured yet)"
    return summary + "."


def _format_trend_summary(trend_points: list[dict]) -> str:
    """Deterministic direction judgment — never left to the AI to infer from
    raw counts, so 'improving'/'deteriorating' in the narrative is always
    traceable to this exact comparison."""
    if len(trend_points) < 2:
        return "No prior snapshot exists yet, so no trend comparison is available."
    previous, current = trend_points[-2], trend_points[-1]

    def pressure(point: dict) -> int:
        return point["extreme"] * 3 + point["high"] * 2 + point["moderate"]

    if pressure(current) < pressure(previous):
        direction = "improving"
    elif pressure(current) > pressure(previous):
        direction = "deteriorating"
    else:
        direction = "holding steady"
    return (
        f"Versus the '{previous['label']}' snapshot ({previous['period_end']}): extreme risks "
        f"went from {previous['extreme']} to {current['extreme']}, high risks from "
        f"{previous['high']} to {current['high']}, total open risks from "
        f"{previous['total_risks']} to {current['total_risks']}. Overall risk pressure is {direction}."
    )


def _format_horizon_summary(session: Session) -> str:
    """Unresolved Emerging Risk Radar candidates (Milestone 9) — the closest
    thing this platform has to a real 'signals on the horizon' feed, so the
    executive summary treats it as the horizon-watch source of truth rather
    than asking the model to invent one."""
    candidates = session.scalars(
        select(EmergingRiskCandidate)
        .where(
            EmergingRiskCandidate.lifecycle_status.in_(
                [CandidateLifecycleStatus.CANDIDATE, CandidateLifecycleStatus.UNDER_REVIEW]
            )
        )
        .order_by(EmergingRiskCandidate.created_at.desc())
    ).all()
    if not candidates:
        return "No unresolved Emerging Risk Radar signals at this time."
    titles = "; ".join(
        f"{c.title} ({c.category.name if c.category else 'Uncategorized'})" for c in candidates[:5]
    )
    return f"{len(candidates)} unresolved emerging-risk signal(s) under review, including: {titles}."


def build_executive_summary_context(session: Session) -> dict:
    dashboard = compute_executive_dashboard(session)
    governance = compute_governance_health(session)
    trend_points = compute_trend(session)

    return {
        "total_risks": dashboard["total_risks"],
        "extreme_count": dashboard["extreme_count"],
        "high_count": dashboard["high_count"],
        "moderate_count": dashboard["moderate_count"],
        "low_count": dashboard["low_count"],
        "unscored_count": dashboard["unscored_count"],
        "weak_controls_count": dashboard["weak_controls_count"],
        "overdue_actions_count": dashboard["overdue_actions_count"],
        "overdue_reviews_count": governance["overdue_reviews_count"],
        "risks_outside_appetite_count": dashboard["risks_outside_appetite_count"],
        "top_risk_titles": [r["title"] for r in dashboard["top_risks"][:5]],
        "top_risks_block": _format_top_risks_block(dashboard["top_risks"]),
        "category_exposure_block": _format_category_exposure_block(dashboard["category_exposure"]),
        "appetite_summary": _format_appetite_summary(governance["appetite_status_counts"]),
        "breach_risk_titles": (
            "; ".join(r["title"] for r in governance["breach_risks"][:5]) or "none currently"
        ),
        "trend_summary": _format_trend_summary(trend_points),
        "horizon_summary": _format_horizon_summary(session),
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


def build_control_gap_context(session: Session, risk: Risk) -> dict:
    """Allow-listed projection of one risk plus its linked controls — only
    the fields listed here ever reach a prompt."""
    controls = session.scalars(
        select(Control).join(RiskControl, RiskControl.control_id == Control.id).where(
            RiskControl.risk_id == risk.id
        )
    ).all()
    linked_controls = [
        {
            "name": c.name,
            "control_type": c.control_type.value,
            "design_effectiveness": c.design_effectiveness,
            "operating_effectiveness": c.operating_effectiveness,
        }
        for c in controls
    ]
    controls_block = (
        "\n".join(
            f"- {c['name']} ({c['control_type']}): design={c['design_effectiveness']}, "
            f"operating={c['operating_effectiveness']}"
            for c in linked_controls
        )
        or "(none)"
    )

    return {
        "title": risk.title,
        "category": risk.category.name if risk.category else "Uncategorized",
        "residual_band": risk.residual_band.value if risk.residual_band else None,
        "control_count": len(linked_controls),
        "controls_block": controls_block,
        "linked_controls": linked_controls,
    }


def _category_risk_counts(session: Session) -> dict[str, int]:
    """Every taxonomy category's registered-risk count, including
    categories with zero risks — a coverage-gap signal a dashboard's
    occupied-categories-only exposure list can't show."""
    categories = session.scalars(select(RiskCategory)).all()
    name_by_id = {c.id: c.name for c in categories}
    counts = {c.name: 0 for c in categories}
    for (category_id,) in session.execute(select(Risk.category_id)):
        name = name_by_id.get(category_id)
        if name is not None:
            counts[name] += 1
    return counts


def build_emerging_risk_context(session: Session) -> dict:
    """Allow-listed: category names and counts (real, computed data) plus
    existing risk titles only (never full statements) — enough for a
    provider to avoid duplicating a risk already on file, without handing
    it more of the register than it needs."""
    category_counts = _category_risk_counts(session)
    existing_titles = list(session.scalars(select(Risk.title)))
    return {
        "category_counts": category_counts,
        "category_summary": ", ".join(f"{name}: {count}" for name, count in sorted(category_counts.items()))
        or "(no categories configured)",
        "existing_titles": "\n".join(f"- {t}" for t in existing_titles) or "(none)",
    }


def build_market_analysis_context(session: Session) -> dict:
    """Allow-listed: category exposure counts only — no external
    market/news data source exists in this prototype, so this context is
    deliberately limited to what the register itself contains."""
    category_counts = _category_risk_counts(session)
    return {
        "category_counts": category_counts,
        "category_summary": ", ".join(f"{name}: {count}" for name, count in sorted(category_counts.items()))
        or "(no categories configured)",
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


def _persist_suggestions(
    session: Session, run: AIRun, response: AIResponse, *, risk_id: uuid.UUID | None
) -> None:
    now = datetime.now(timezone.utc)
    for draft in response.suggestions:
        session.add(
            AISuggestion(
                run_id=run.id,
                risk_id=risk_id,
                suggestion_type=draft.suggestion_type,
                summary=draft.summary,
                rationale=draft.rationale,
                proposed_changes=draft.proposed_changes,
                human_review_status=AISuggestionReviewStatus.PENDING,
                created_at=now,
            )
        )


def execute_risk_analysis(session: Session, provider: AIProvider, run: AIRun, *, risk: Risk) -> None:
    """Fills in a pending risk-analysis `AIRun` in place and persists any
    suggestions the provider drafted, each `pending` review. Caller (the
    worker job) commits."""
    context = build_risk_analysis_context(session, risk)
    response = provider.analyze_risk(context)
    _apply_response(run, response)
    _persist_suggestions(session, run, response, risk_id=risk.id)


def execute_control_gap_analysis(session: Session, provider: AIProvider, run: AIRun, *, risk: Risk) -> None:
    """Fills in a pending control-gap-analysis `AIRun` in place and
    persists any `new_control` suggestion the provider drafted."""
    context = build_control_gap_context(session, risk)
    response = provider.analyze_control_gaps(context)
    _apply_response(run, response)
    _persist_suggestions(session, run, response, risk_id=risk.id)


def execute_emerging_risk_scan(session: Session, provider: AIProvider, run: AIRun) -> None:
    """Fills in a pending emerging-risk-scan `AIRun` in place and persists
    any `new_risk` suggestion the provider drafted. `risk_id` is null on
    the suggestion — by definition there is no existing risk yet."""
    context = build_emerging_risk_context(session)
    response = provider.scan_emerging_risks(context)
    _apply_response(run, response)
    _persist_suggestions(session, run, response, risk_id=None)


def execute_market_analysis(session: Session, provider: AIProvider, run: AIRun) -> None:
    """Fills in a pending market-analysis `AIRun` in place. Narrative only
    — this capability never produces a suggestion, since there is no
    concrete change for a human to approve, only commentary."""
    context = build_market_analysis_context(session)
    response = provider.generate_market_analysis(context)
    _apply_response(run, response)


def _match_category_id(session: Session, category_name: str | None) -> uuid.UUID | None:
    if not category_name:
        return None
    category = session.scalars(
        select(RiskCategory).where(func.lower(RiskCategory.name) == category_name.strip().lower())
    ).first()
    return category.id if category else None


def _approve_assessment_change(
    session: Session, suggestion: AISuggestion, *, reviewer_id: uuid.UUID, actor_email: str
) -> Risk:
    """Fields the suggestion doesn't mention keep the risk's current
    values, read from its latest assessment rather than assumed."""
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

    return update_risk(
        session,
        risk=risk,
        expected_version=risk.version,
        field_updates={},
        assessment_input=assessment_input,
        actor_email=actor_email,
        actor_id=reviewer_id,
        source="ai-approved",
    )


def _approve_new_control(
    session: Session, suggestion: AISuggestion, *, reviewer_id: uuid.UUID, actor_email: str
) -> Control:
    """Creates the suggested control via the same path interactive control
    creation uses, then links it to the risk the suggestion was drafted
    for — the only write this suggestion type can ever make."""
    changes = suggestion.proposed_changes
    try:
        control_type = ControlType((changes.get("control_type") or "preventive").lower())
    except ValueError:
        control_type = ControlType.PREVENTIVE

    control = create_control(
        session,
        fields=ControlFields(
            name=changes.get("name") or "AI-suggested control",
            control_type=control_type,
            automation=ControlAutomation.MANUAL,
            description=changes.get("description"),
        ),
        actor_email=actor_email,
        actor_id=reviewer_id,
        source="ai-approved",
    )
    session.add(RiskControl(risk_id=suggestion.risk_id, control_id=control.id))
    record_audit_event(
        session,
        actor=actor_email,
        entity="risk",
        entity_id=suggestion.risk_id,
        action="link_control",
        old_value=None,
        new_value={"control_id": str(control.id)},
        source="ai-approved",
    )
    return control


def _approve_new_risk(session: Session, suggestion: AISuggestion, *, reviewer_id: uuid.UUID, actor_email: str) -> Risk:
    """Creates the suggested risk with a deliberately minimal, unrated
    placeholder assessment — AI never assigns a real likelihood/impact
    score, per ADR 0006; a human must record the actual assessment."""
    changes = suggestion.proposed_changes
    fields = RiskFields(
        title=changes.get("title") or "AI-suggested risk",
        statement=changes.get("statement"),
        category_id=_match_category_id(session, changes.get("category")),
        status="draft",
        decision="pending",
        latest_update=(
            "Created from an approved AI emerging-risk suggestion. The likelihood and impact "
            "scores are an unrated placeholder — a Risk Owner must record a real assessment "
            "before this risk's score reflects anything meaningful."
        ),
    )
    assessment_input = AssessmentInput(
        likelihood=1,
        impact_financial=1,
        impact_customer_service=1,
        impact_operational_delivery=1,
        impact_legal_regulatory=1,
        impact_reputation=1,
        impact_health_safety=1,
        control_effectiveness=None,
    )
    return create_risk(
        session,
        fields=fields,
        assessment_input=assessment_input,
        actor_email=actor_email,
        actor_id=reviewer_id,
        source="ai-approved",
    )


def approve_suggestion(
    session: Session,
    suggestion: AISuggestion,
    *,
    reviewer_id: uuid.UUID,
    actor_email: str,
) -> Risk | Control:
    """Applies `proposed_changes` through the normal, audited service-layer
    path for the suggestion's own type — the only code path in this
    codebase that can turn an AI suggestion into an actual change, per
    ADR 0006."""
    if suggestion.human_review_status != AISuggestionReviewStatus.PENDING:
        raise SuggestionAlreadyReviewedError(suggestion.id)

    if suggestion.suggestion_type == "new_control":
        result: Risk | Control = _approve_new_control(
            session, suggestion, reviewer_id=reviewer_id, actor_email=actor_email
        )
    elif suggestion.suggestion_type == "new_risk":
        result = _approve_new_risk(session, suggestion, reviewer_id=reviewer_id, actor_email=actor_email)
    else:
        result = _approve_assessment_change(session, suggestion, reviewer_id=reviewer_id, actor_email=actor_email)

    suggestion.human_review_status = AISuggestionReviewStatus.APPROVED
    suggestion.reviewed_by_id = reviewer_id
    suggestion.reviewed_at = datetime.now(timezone.utc)
    return result


def reject_suggestion(session: Session, suggestion: AISuggestion, *, reviewer_id: uuid.UUID) -> None:
    if suggestion.human_review_status != AISuggestionReviewStatus.PENDING:
        raise SuggestionAlreadyReviewedError(suggestion.id)

    suggestion.human_review_status = AISuggestionReviewStatus.REJECTED
    suggestion.reviewed_by_id = reviewer_id
    suggestion.reviewed_at = datetime.now(timezone.utc)
