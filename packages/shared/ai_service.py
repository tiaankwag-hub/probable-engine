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
from packages.shared.appetite_repo import compute_appetite_status_for_risk
from packages.shared.audit import record_audit_event
from packages.shared.control_service import ControlFields, create_control
from packages.shared.dashboard_service import compute_executive_dashboard
from packages.shared.governance_service import NON_TERMINAL_ACTION_STATUSES, compute_governance_health
from packages.shared.models.action import Action, ActionStatus
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
from packages.shared.models.issue import Issue, IssueStatus
from packages.shared.models.risk import Risk, RiskCategory
from packages.shared.risk_service import (
    AssessmentInput,
    RiskFields,
    create_risk,
    find_category_by_name,
    update_risk,
)
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


def _format_controls_block(controls: list[Control]) -> str:
    if not controls:
        return "(none linked)"
    lines = []
    for c in controls:
        latest_test = c.tests[0] if c.tests else None
        if latest_test:
            test_note = f", last tested {latest_test.test_date} ({latest_test.result.value}"
            if latest_test.finding:
                test_note += f" — {latest_test.finding}"
            test_note += ")"
        elif c.last_tested:
            test_note = f", last tested {c.last_tested}"
        else:
            test_note = ", never tested"
        lines.append(
            f"- {c.name} ({c.control_type.value}, {c.automation.value}): "
            f"design={c.design_effectiveness}, operating={c.operating_effectiveness}{test_note}"
        )
    return "\n".join(lines)


def _format_incidents_block(incidents: list[Incident]) -> str:
    if not incidents:
        return "(none recorded)"
    lines = []
    for i in incidents[:5]:
        flag = " — flagged as suggesting a likelihood increase" if i.suggests_likelihood_increase else ""
        lines.append(f"- {i.incident_date} ({i.severity.value}): {i.description}{flag}")
    return "\n".join(lines)


def _format_actions_block(actions: list[Action], *, today: date) -> str:
    if not actions:
        return "(none open)"
    lines = []
    for a in actions:
        overdue = (
            f", {(today - a.due_date).days} day(s) overdue"
            if a.due_date and a.due_date < today
            else ""
        )
        lines.append(f"- {a.title} ({a.priority.value}, {a.status.value}, {a.completion_percent}% complete{overdue})")
    return "\n".join(lines)


def _format_issues_block(issues: list[Issue]) -> str:
    if not issues:
        return "(none open)"
    return "\n".join(f"- {i.description}" for i in issues[:5])


def _format_assessment_trend(assessments: list) -> str:
    if len(assessments) < 2:
        return "Only one assessment on file — no trend to compare against."
    current, previous = assessments[0], assessments[1]
    return (
        f"Previous assessment ({previous.assessed_at.date()}): likelihood {previous.likelihood}, "
        f"residual {previous.residual_score} "
        f"({previous.residual_band.value if previous.residual_band else 'n/a'}). "
        f"Current: likelihood {current.likelihood}, residual {current.residual_score} "
        f"({current.residual_band.value if current.residual_band else 'n/a'})."
    )


def build_risk_analysis_context(session: Session, risk: Risk) -> dict:
    """Allow-listed projection of one risk and everything a human analyst
    would actually look at before assessing it — the full narrative, its
    real control landscape (including test findings, not just a
    effectiveness number), actual incident/action/issue detail rather than
    bare counts, and how the assessment has trended. Only the fields
    listed here ever reach a prompt, regardless of what else `Risk`
    carries."""
    today = date.today()

    incidents = session.scalars(
        select(Incident).where(Incident.risk_id == risk.id).order_by(Incident.incident_date.desc())
    ).all()
    open_actions = session.scalars(
        select(Action)
        .where(Action.risk_id == risk.id, Action.status.in_(NON_TERMINAL_ACTION_STATUSES))
        .order_by(Action.due_date)
    ).all()
    overdue_action_count = sum(1 for a in open_actions if a.due_date and a.due_date < today)
    open_issues = session.scalars(
        select(Issue).where(Issue.risk_id == risk.id, Issue.status == IssueStatus.OPEN)
    ).all()
    controls = session.scalars(
        select(Control)
        .join(RiskControl, RiskControl.control_id == Control.id)
        .where(RiskControl.risk_id == risk.id)
    ).all()
    appetite_status = compute_appetite_status_for_risk(session, risk).replace("_", " ")

    return {
        "title": risk.title,
        "statement": risk.statement or "(none provided)",
        "cause": risk.cause or "(not specified)",
        "event": risk.event or "(not specified)",
        "impact": risk.impact or "(not specified)",
        "category": risk.category.name if risk.category else "Uncategorized",
        "department": risk.department or "(not specified)",
        "likelihood": risk.likelihood,
        "overall_impact": risk.overall_impact,
        "inherent_score": risk.inherent_score,
        "inherent_band": risk.inherent_band.value if risk.inherent_band else None,
        "control_effectiveness": risk.control_effectiveness,
        "residual_score": risk.residual_score,
        "residual_band": risk.residual_band.value if risk.residual_band else None,
        "decision": risk.decision.value if risk.decision else None,
        "velocity": risk.velocity or "(not specified)",
        "confidence": risk.confidence or "(not specified)",
        "appetite_status": appetite_status,
        "control_count": len(controls),
        "controls_block": _format_controls_block(controls),
        "recent_incident_count": len(incidents),
        "incidents_block": _format_incidents_block(incidents),
        "overdue_action_count": overdue_action_count,
        "open_actions_block": _format_actions_block(open_actions, today=today),
        "open_issues_block": _format_issues_block(open_issues),
        "assessment_trend": _format_assessment_trend(list(risk.assessments)),
    }


def build_control_gap_context(session: Session, risk: Risk) -> dict:
    """Allow-listed projection of one risk plus its linked controls — the
    full control picture (test history and findings, not just an
    effectiveness number) and what the controls actually need to
    mitigate, not just the risk's title. Only the fields listed here ever
    reach a prompt."""
    today = date.today()
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
            "latest_test_result": c.tests[0].result.value if c.tests else None,
            "latest_test_finding": c.tests[0].finding if c.tests else None,
            "overdue_for_test": bool(c.next_test and c.next_test < today),
        }
        for c in controls
    ]

    return {
        "title": risk.title,
        "statement": risk.statement or "(none provided)",
        "cause": risk.cause or "(not specified)",
        "event": risk.event or "(not specified)",
        "impact": risk.impact or "(not specified)",
        "category": risk.category.name if risk.category else "Uncategorized",
        "residual_score": risk.residual_score,
        "residual_band": risk.residual_band.value if risk.residual_band else None,
        "control_count": len(linked_controls),
        "controls_block": _format_controls_block(controls),
        "linked_controls": linked_controls,
    }


def _category_stats(session: Session) -> dict[str, dict]:
    """Every taxonomy category's registered-risk count and average
    residual score, including categories with zero risks — the strongest
    possible coverage-gap signal, and one a risks-only iteration would
    miss entirely for a category that has none."""
    categories = session.scalars(select(RiskCategory)).all()
    name_by_id = {c.id: c.name for c in categories}
    stats = {c.name: {"count": 0, "score_sum": 0.0, "score_n": 0} for c in categories}
    for category_id, residual_score in session.execute(select(Risk.category_id, Risk.residual_score)):
        name = name_by_id.get(category_id)
        if name is None:
            continue
        stats[name]["count"] += 1
        if residual_score is not None:
            stats[name]["score_sum"] += residual_score
            stats[name]["score_n"] += 1
    return {
        name: {
            "count": s["count"],
            "avg_residual": round(s["score_sum"] / s["score_n"], 2) if s["score_n"] else None,
        }
        for name, s in stats.items()
    }


def _format_category_stats_block(category_stats: dict[str, dict]) -> str:
    if not category_stats:
        return "(no categories configured)"
    parts = []
    for name, s in sorted(category_stats.items()):
        avg = f"{s['avg_residual']:.1f}" if s["avg_residual"] is not None else "n/a"
        parts.append(f"{name}: {s['count']} risk(s), avg residual {avg}")
    return "; ".join(parts)


def build_emerging_risk_context(session: Session) -> dict:
    """Allow-listed: category names, counts, and average severity (real,
    computed data) plus existing risk titles only (never full statements)
    — enough for a provider to judge which category is genuinely
    under-covered (fewest risks *and* already the least severe is a much
    stronger under-identification signal than count alone) without
    duplicating a risk already on file."""
    category_stats = _category_stats(session)
    category_counts = {name: s["count"] for name, s in category_stats.items()}
    existing_titles = list(session.scalars(select(Risk.title)))
    return {
        "category_counts": category_counts,
        "category_stats": category_stats,
        "category_summary": _format_category_stats_block(category_stats),
        "existing_titles": "\n".join(f"- {t}" for t in existing_titles) or "(none)",
    }


def build_market_analysis_context(session: Session) -> dict:
    """Allow-listed: category exposure counts, average severity, and the
    portfolio's top risks by residual score — no external market/news
    data source exists in this prototype, so this context is deliberately
    limited to what the register itself contains, but detailed enough
    (severity and specific risks, not just headcounts) for commentary
    that engages with this organization's actual exposure rather than a
    generic industry summary."""
    category_stats = _category_stats(session)
    category_counts = {name: s["count"] for name, s in category_stats.items()}
    top_risks = compute_executive_dashboard(session)["top_risks"][:5]
    return {
        "category_counts": category_counts,
        "category_summary": _format_category_stats_block(category_stats),
        "top_risks_block": _format_top_risks_block(top_risks),
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
        category_id=find_category_by_name(session, changes.get("category")),
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
