"""Deterministic, network-free AI provider (ADR 0006) — never calls out
to any model, so local development and CI never require credentials.
Output is templated from the same context dict the real provider
receives, so the two are interchangeable in every caller.
"""

from __future__ import annotations

import time
from typing import Any

from packages.ai.provider import AIResponse, CandidateAssessment, IntakeTurnResult, SuggestionDraft

MOCK_MODEL_NAME = "mock-analyst-v1"


def _generate_executive_summary(context: dict[str, Any]) -> AIResponse:
    start = time.monotonic()
    total = context.get("total_risks", 0)
    extreme = context.get("extreme_count", 0)
    high = context.get("high_count", 0)
    weak_controls = context.get("weak_controls_count", 0)
    overdue_actions = context.get("overdue_actions_count", 0)
    overdue_reviews = context.get("overdue_reviews_count", 0)
    outside_appetite = context.get("risks_outside_appetite_count", 0)
    top_risk_titles = context.get("top_risk_titles", [])
    category_exposure_block = context.get("category_exposure_block", "(no risks registered)")
    appetite_summary = context.get("appetite_summary", "Appetite position unavailable.")
    breach_risk_titles = context.get("breach_risk_titles", "none currently")
    trend_summary = context.get("trend_summary", "No trend data available.")
    horizon_summary = context.get("horizon_summary", "No horizon-watch data available.")

    # Paragraph 1: headline posture — what's good, what's bad.
    p1 = [
        f"The register currently holds {total} open risk(s): {extreme} rated Extreme and "
        f"{high} rated High."
    ]
    if not extreme and not high:
        p1.append("No risk currently sits at the two highest bands, which is the strongest possible starting point.")
    if weak_controls or overdue_actions or overdue_reviews:
        p1.append(
            f"On the control side, {weak_controls} control(s) are rated weak, "
            f"{overdue_actions} remediation action(s) are overdue, and {overdue_reviews} review(s) "
            "are past due — the operational gaps behind any residual exposure above."
        )
    else:
        p1.append("Control health is currently clean: no weak controls, overdue actions, or overdue reviews on file.")
    p1.append(f"Exposure by category: {category_exposure_block}.")

    # Paragraph 2: focus + trajectory + appetite.
    p2 = [f"Risk appetite position: {appetite_summary}"]
    if outside_appetite:
        p2.append(f"Leadership should focus first on risks requiring attention: {breach_risk_titles}.")
    elif top_risk_titles:
        p2.append("With nothing currently outside appetite, ongoing focus should stay on the highest residual "
                   f"items: {'; '.join(top_risk_titles[:3])}.")
    p2.append(trend_summary)

    # Paragraph 3: horizon watch, inside and outside the organization.
    p3 = [
        horizon_summary,
        "This is a deterministic mock summary, not a generative one, so it does not offer "
        "external market/regulatory judgment beyond the category exposure above — configure a "
        "real provider (e.g. set GEMINI_API_KEY) for that layer of commentary.",
    ]

    text = "\n\n".join([" ".join(p1), " ".join(p2), " ".join(p3)])
    return AIResponse(text=text, model=MOCK_MODEL_NAME, latency_ms=int((time.monotonic() - start) * 1000))


def _analyze_risk(context: dict[str, Any]) -> AIResponse:
    start = time.monotonic()
    title = context.get("title", "This risk")
    residual_band = context.get("residual_band")
    likelihood = context.get("likelihood")
    control_effectiveness = context.get("control_effectiveness")
    recent_incident_count = context.get("recent_incident_count", 0)
    overdue_action_count = context.get("overdue_action_count", 0)

    text = f'"{title}" is currently assessed at a residual band of {residual_band or "not yet scored"}.'
    suggestions: list[SuggestionDraft] = []

    if recent_incident_count and likelihood is not None and likelihood < 5:
        proposed_likelihood = min(5, likelihood + 1)
        text += (
            f" {recent_incident_count} recent incident(s) are linked to this risk, which is "
            "not yet reflected in its likelihood rating."
        )
        suggestions.append(
            SuggestionDraft(
                suggestion_type="assessment_change",
                summary=f"Increase likelihood to {proposed_likelihood}",
                rationale=(
                    f"{recent_incident_count} recorded incident(s) since the last assessment "
                    "suggest this risk is materializing more often than currently modeled."
                ),
                proposed_changes={"likelihood": proposed_likelihood},
            )
        )
    elif overdue_action_count and control_effectiveness is not None and control_effectiveness > 1:
        proposed_effectiveness = control_effectiveness - 1
        text += (
            f" {overdue_action_count} remediation action(s) for this risk are overdue, which "
            "casts doubt on the currently modeled control effectiveness."
        )
        suggestions.append(
            SuggestionDraft(
                suggestion_type="assessment_change",
                summary=f"Reduce control effectiveness to {proposed_effectiveness}",
                rationale=(
                    f"{overdue_action_count} overdue remediation action(s) suggest the controls "
                    "this rating assumes are not yet fully in place."
                ),
                proposed_changes={"control_effectiveness": proposed_effectiveness},
            )
        )
    elif control_effectiveness is not None and control_effectiveness <= 2:
        text += " Control effectiveness is already weak and may be understating residual exposure."

    return AIResponse(
        text=text,
        model=MOCK_MODEL_NAME,
        latency_ms=int((time.monotonic() - start) * 1000),
        suggestions=suggestions,
    )


def _is_weak(control: dict[str, Any]) -> bool:
    design = control.get("design_effectiveness")
    operating = control.get("operating_effectiveness")
    ratings = [r for r in (design, operating) if r is not None]
    return bool(ratings) and all(r <= 2 for r in ratings)


def _analyze_control_gaps(context: dict[str, Any]) -> AIResponse:
    start = time.monotonic()
    title = context.get("title", "This risk")
    category = context.get("category") or "Uncategorized"
    linked_controls: list[dict[str, Any]] = context.get("linked_controls", [])

    suggestions: list[SuggestionDraft] = []
    if not linked_controls:
        text = f'"{title}" has no linked control at all — residual exposure is currently unmitigated.'
        suggestions.append(
            SuggestionDraft(
                suggestion_type="new_control",
                summary=f"Add a control for {title}",
                rationale=(
                    f'No control is currently linked to "{title}", so its residual score reflects '
                    "no mitigation at all. A first control, even a basic preventive one, would give "
                    "this risk a more realistic residual rating."
                ),
                proposed_changes={
                    "name": f"{category} control for {title}",
                    "control_type": "preventive",
                    "description": f"Draft control proposed by AI analysis to address {title}.",
                },
            )
        )
    elif all(_is_weak(c) for c in linked_controls):
        text = (
            f'"{title}" has {len(linked_controls)} linked control(s), but all are rated weak '
            "(design or operating effectiveness of 2 or below)."
        )
        suggestions.append(
            SuggestionDraft(
                suggestion_type="new_control",
                summary=f"Add a compensating control for {title}",
                rationale=(
                    f"Every control currently linked to \"{title}\" is rated weak, which suggests "
                    "a compensating control is needed rather than relying on the existing ones alone."
                ),
                proposed_changes={
                    "name": f"Compensating {category} control for {title}",
                    "control_type": "detective",
                    "description": f"Draft compensating control proposed by AI analysis for {title}.",
                },
            )
        )
    else:
        text = (
            f'"{title}" has {len(linked_controls)} linked control(s) and at least one is rated '
            "adequately — no control gap identified."
        )

    return AIResponse(
        text=text, model=MOCK_MODEL_NAME, latency_ms=int((time.monotonic() - start) * 1000),
        suggestions=suggestions,
    )


# Deliberately not a live signal feed (none exists in this prototype) — a
# small, fixed set of well-known emerging-risk archetypes keyed by the
# taxonomy category they'd fall under, so the mock can deterministically
# propose one for whichever category the current portfolio covers least.
EMERGING_RISK_CANDIDATES: dict[str, tuple[str, str]] = {
    "Operational": (
        "Key-person dependency in critical operations",
        "Reliance on a small number of individuals for critical operational knowledge, with no documented succession plan.",
    ),
    "Financial": (
        "Interest rate volatility on variable-rate obligations",
        "Exposure to rising interest rates on variable-rate debt or financing arrangements not yet hedged.",
    ),
    "Cyber & Information Security": (
        "Supply-chain compromise via a third-party software dependency",
        "A compromised upstream software dependency could introduce a vulnerability without a corresponding code change on our side.",
    ),
    "Legal & Regulatory": (
        "Emerging AI/ML regulation affecting current data practices",
        "New or proposed AI/data-protection regulation in jurisdictions we operate in may require changes to current data practices.",
    ),
    "Strategic": (
        "Disruptive entrant using a materially lower cost structure",
        "A new market entrant with a structurally lower cost base could erode margins faster than the current strategy assumes.",
    ),
    "People & Culture": (
        "Skills gap in an emerging technical capability",
        "Demand for a newly critical technical skill set may outpace internal hiring and training capacity.",
    ),
    "Third Party & Vendor": (
        "Concentration risk in a single critical vendor",
        "Heavy reliance on one vendor for a critical service, with no evaluated fallback if that vendor fails to deliver.",
    ),
}


def _scan_emerging_risks(context: dict[str, Any]) -> AIResponse:
    start = time.monotonic()
    category_counts: dict[str, int] = context.get("category_counts", {})

    suggestions: list[SuggestionDraft] = []
    if not category_counts:
        text = "No risks are currently registered, so no category coverage comparison is possible."
    else:
        least_covered = min(category_counts.items(), key=lambda item: (item[1], item[0]))[0]
        candidate = EMERGING_RISK_CANDIDATES.get(least_covered)
        if candidate is None:
            text = (
                f'"{least_covered}" is the least-represented category in the register '
                f"({category_counts[least_covered]} risk(s)), but no emerging-risk archetype is "
                "on file for it."
            )
        else:
            title, statement = candidate
            text = (
                f'"{least_covered}" is the least-represented category in the register '
                f"({category_counts[least_covered]} risk(s)), suggesting a possible coverage gap."
            )
            suggestions.append(
                SuggestionDraft(
                    suggestion_type="new_risk",
                    summary=f"Consider adding: {title}",
                    rationale=(
                        f'"{least_covered}" has fewer registered risks than any other category '
                        f"({category_counts[least_covered]}), and this is a commonly seen risk in "
                        "that category that isn't obviously represented yet."
                    ),
                    proposed_changes={"title": title, "statement": statement, "category": least_covered},
                )
            )

    return AIResponse(
        text=text, model=MOCK_MODEL_NAME, latency_ms=int((time.monotonic() - start) * 1000),
        suggestions=suggestions,
    )


def _generate_market_analysis(context: dict[str, Any]) -> AIResponse:
    start = time.monotonic()
    category_counts: dict[str, int] = context.get("category_counts", {})
    summary = ", ".join(f"{name} ({count})" for name, count in sorted(category_counts.items()))
    text = (
        "No live market-analysis capability is available from the deterministic mock provider — "
        "this prototype has no external market/news data source configured. Portfolio category "
        f"exposure on file: {summary or 'no risks registered'}. Configure a real provider "
        "(e.g. set GEMINI_API_KEY) to receive AI-generated industry/market commentary grounded in "
        "the model's own general knowledge."
    )
    return AIResponse(text=text, model=MOCK_MODEL_NAME, latency_ms=int((time.monotonic() - start) * 1000))


def _first_sentence(text: str, *, max_len: int = 100) -> str:
    sentence = text.split(". ")[0].rstrip(".")
    return sentence if len(sentence) <= max_len else sentence[: max_len - 1].rstrip() + "…"


def _analyze_signal(context: dict[str, Any]) -> CandidateAssessment:
    start = time.monotonic()
    content = context.get("content", "")
    category = context.get("classified_category")
    existing_titles: list[str] = context.get("existing_category_risk_titles", [])

    if category is None:
        return CandidateAssessment(
            is_relevant=False,
            title="",
            summary="",
            relevance_assessment="Signal did not match any known risk category; not proposed as a candidate.",
            model=MOCK_MODEL_NAME,
            latency_ms=int((time.monotonic() - start) * 1000),
        )

    assessment = (
        f"Classified under {category}. "
        + (
            f"{len(existing_titles)} existing risk(s) are already registered in this category "
            "but none obviously cover this specific signal."
            if existing_titles
            else f"No existing risks are currently registered under {category}, so this may be a coverage gap."
        )
    )
    return CandidateAssessment(
        is_relevant=True,
        title=_first_sentence(content),
        summary=content,
        relevance_assessment=assessment,
        model=MOCK_MODEL_NAME,
        latency_ms=int((time.monotonic() - start) * 1000),
    )


# Fixed backbone of questions for the Guided Risk Intake mock — a real
# provider phrases these adaptively and asks a clarifying follow-up on a
# vague answer, but the mock just walks this list in order, one field per
# turn, so it stays deterministic and needs no network call.
INTAKE_FIELD_SEQUENCE = ["event", "impact", "cause", "department_guess", "category_guess", "title"]
INTAKE_QUESTIONS: dict[str, str] = {
    "event": "In your own words, what's the risk or concern — what could go wrong, or what have you noticed?",
    "impact": "If that happened, what would it actually affect or cost us — customers, money, downtime, reputation?",
    "cause": "Why do you think this could happen — what's driving it?",
    "department_guess": "Which team or part of the business does this mainly affect?",
    "category_guess": "Which of these best fits it: {categories}?",
    "title": "Last one — if you had to give this a short name, what would you call it?",
}


def _generate_intake_turn(context: dict[str, Any]) -> IntakeTurnResult:
    start = time.monotonic()
    turn_number = context.get("turn_number", 1)
    latest_message = (context.get("latest_user_message") or "").strip()
    category_names: list[str] = context.get("category_names", [])

    field_index = min(turn_number, len(INTAKE_FIELD_SEQUENCE)) - 1
    field_just_answered = INTAKE_FIELD_SEQUENCE[field_index]

    updated_fields: dict[str, str] = {}
    if latest_message:
        if field_just_answered == "category_guess" and category_names:
            match = next((c for c in category_names if c.lower() in latest_message.lower()), None)
            updated_fields["category_guess"] = match or latest_message
        else:
            updated_fields[field_just_answered] = latest_message

    next_index = field_index + 1
    if next_index >= len(INTAKE_FIELD_SEQUENCE):
        merged = {**context.get("draft_fields", {}), **updated_fields}
        summary = "; ".join(f"{k.replace('_', ' ')}: {v}" for k, v in merged.items() if v)
        reply_message = (
            f"Thanks — here's what I've got: {summary}. Does that look right? Submit it below "
            "for a Risk Manager to review, or keep chatting to add more detail."
        )
        is_ready = True
    else:
        next_field = INTAKE_FIELD_SEQUENCE[next_index]
        question = INTAKE_QUESTIONS[next_field]
        if next_field == "category_guess":
            question = question.format(categories=", ".join(category_names) or "no categories configured")
        reply_message = question
        is_ready = False

    return IntakeTurnResult(
        reply_message=reply_message,
        updated_fields=updated_fields,
        is_ready_to_submit=is_ready,
        model=MOCK_MODEL_NAME,
        latency_ms=int((time.monotonic() - start) * 1000),
    )


class MockAIProvider:
    def generate_executive_summary(self, context: dict[str, Any]) -> AIResponse:
        return _generate_executive_summary(context)

    def analyze_risk(self, context: dict[str, Any]) -> AIResponse:
        return _analyze_risk(context)

    def analyze_control_gaps(self, context: dict[str, Any]) -> AIResponse:
        return _analyze_control_gaps(context)

    def scan_emerging_risks(self, context: dict[str, Any]) -> AIResponse:
        return _scan_emerging_risks(context)

    def generate_market_analysis(self, context: dict[str, Any]) -> AIResponse:
        return _generate_market_analysis(context)

    def analyze_signal(self, context: dict[str, Any]) -> CandidateAssessment:
        return _analyze_signal(context)

    def continue_risk_intake(self, context: dict[str, Any]) -> IntakeTurnResult:
        return _generate_intake_turn(context)
