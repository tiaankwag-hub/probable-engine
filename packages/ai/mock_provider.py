"""Deterministic, network-free AI provider (ADR 0006) — never calls out
to any model, so local development and CI never require credentials.
Output is templated from the same context dict the real provider
receives, so the two are interchangeable in every caller.
"""

from __future__ import annotations

import time
from typing import Any

from packages.ai.provider import AIResponse, SuggestionDraft

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


class MockAIProvider:
    def generate_executive_summary(self, context: dict[str, Any]) -> AIResponse:
        return _generate_executive_summary(context)

    def analyze_risk(self, context: dict[str, Any]) -> AIResponse:
        return _analyze_risk(context)
