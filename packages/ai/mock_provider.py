"""Deterministic, network-free AI provider (ADR 0006) — never calls out
to any model, so local development and CI never require credentials.
Output is templated from the same context dict the real provider
receives, so the two are interchangeable in every caller.
"""

from __future__ import annotations

import time
from typing import Any

from packages.ai.provider import AIResponse, CandidateAssessment, SuggestionDraft

MOCK_MODEL_NAME = "mock-analyst-v1"


def _generate_executive_summary(context: dict[str, Any]) -> AIResponse:
    start = time.monotonic()
    total = context.get("total_risks", 0)
    extreme = context.get("extreme_count", 0)
    high = context.get("high_count", 0)
    weak_controls = context.get("weak_controls_count", 0)
    overdue_actions = context.get("overdue_actions_count", 0)
    outside_appetite = context.get("risks_outside_appetite_count", 0)
    top_risk_titles = context.get("top_risk_titles", [])

    lines = [
        f"The register currently holds {total} open risk(s), including {extreme} rated "
        f"Extreme and {high} rated High."
    ]
    if outside_appetite:
        lines.append(f"{outside_appetite} risk(s) currently sit outside their configured appetite.")
    if weak_controls:
        lines.append(f"{weak_controls} control(s) are operating below an acceptable effectiveness threshold.")
    if overdue_actions:
        lines.append(f"{overdue_actions} remediation action(s) are overdue.")
    if top_risk_titles:
        lines.append("Leadership attention is most warranted on: " + "; ".join(top_risk_titles[:3]) + ".")

    text = " ".join(lines)
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
