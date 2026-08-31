"""Google Generative Language API provider (Milestone 8) — the
prototype's real, network-calling `AIProvider` implementation. Callable
today with a personal Google AI Studio key (`GEMINI_API_KEY`); in
production this becomes `VertexGeminiProvider`, calling the equivalent
Vertex AI endpoint with the same request/response shapes and the same
`AIProvider` interface — only construction (auth + base URL) changes,
never a caller (see the Milestone 8 plan's provider-swap note and ADR
0006).

Prompt builders live in `packages/shared/ai_service.py`, not here: this
module only knows how to turn a finished prompt string into a model
response, never how to build one from ORM data (that boundary is what
keeps prompt-injection/data-leakage review contained to one file, per
`docs/security/threat-model.md`).
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx

from packages.ai.provider import AIResponse, SuggestionDraft

DEFAULT_MODEL = "gemini-2.0-flash"
API_BASE = "https://generativelanguage.googleapis.com/v1beta"
REQUEST_TIMEOUT_SECONDS = 30.0

EXECUTIVE_SUMMARY_PROMPT = """You are a risk management analyst preparing a brief executive summary for a board of directors. Be concise (3-5 sentences), factual, and do not invent numbers beyond what is given below.

Risk register snapshot:
- Total open risks: {total_risks}
- Extreme: {extreme_count}, High: {high_count}, Moderate: {moderate_count}, Low: {low_count}
- Weak controls (effectiveness <= 2/5): {weak_controls_count}
- Overdue remediation actions: {overdue_actions_count}
- Risks outside appetite: {risks_outside_appetite_count}
- Top risks by residual score: {top_risk_titles}

Write the summary now."""

RISK_ANALYSIS_PROMPT = """You are a risk analyst reviewing a single risk register entry. Base your analysis only on the facts given below — do not assume information that isn't provided.

Risk: {title}
Statement: {statement}
Category: {category}
Current likelihood (1-5): {likelihood}
Current control effectiveness (1-5): {control_effectiveness}
Current residual band: {residual_band}
Recent incidents linked to this risk: {recent_incident_count}
Overdue actions linked to this risk: {overdue_action_count}

Write a short (2-4 sentence) narrative analysis. Then decide whether the facts above justify
suggesting a change to the likelihood or control effectiveness rating — only suggest a change
if there is a concrete reason in the facts given (e.g. a recent incident, an overdue critical
action), never as a matter of routine. If you suggest a change, give a one-sentence summary and
a rationale grounded in the specific facts above."""

RISK_ANALYSIS_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "narrative": {"type": "STRING"},
        "should_suggest_change": {"type": "BOOLEAN"},
        "suggestion_summary": {"type": "STRING"},
        "suggestion_rationale": {"type": "STRING"},
        "proposed_likelihood": {"type": "INTEGER", "nullable": True},
        "proposed_control_effectiveness": {"type": "INTEGER", "nullable": True},
    },
    "required": ["narrative", "should_suggest_change"],
}


class GeminiAPIError(RuntimeError):
    pass


class GeminiAPIProvider:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        client: httpx.Client | None = None,
    ):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set")
        self.model = model or os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
        self._client = client or httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS)

    def _generate(self, prompt: str, *, response_schema: dict[str, Any] | None = None) -> tuple[str, int]:
        url = f"{API_BASE}/models/{self.model}:generateContent"
        generation_config: dict[str, Any] = {}
        if response_schema is not None:
            generation_config["responseMimeType"] = "application/json"
            generation_config["responseSchema"] = response_schema

        body: dict[str, Any] = {"contents": [{"parts": [{"text": prompt}]}]}
        if generation_config:
            body["generationConfig"] = generation_config

        start = time.monotonic()
        response = self._client.post(url, params={"key": self.api_key}, json=body)
        latency_ms = int((time.monotonic() - start) * 1000)

        if response.status_code != 200:
            raise GeminiAPIError(f"Gemini API returned {response.status_code}: {response.text[:500]}")

        data = response.json()
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise GeminiAPIError(f"unexpected Gemini API response shape: {data}") from exc

        return text, latency_ms

    def generate_executive_summary(self, context: dict[str, Any]) -> AIResponse:
        prompt = EXECUTIVE_SUMMARY_PROMPT.format(**context)
        text, latency_ms = self._generate(prompt)
        return AIResponse(text=text.strip(), model=self.model, latency_ms=latency_ms)

    def analyze_risk(self, context: dict[str, Any]) -> AIResponse:
        prompt = RISK_ANALYSIS_PROMPT.format(**context)
        raw_text, latency_ms = self._generate(prompt, response_schema=RISK_ANALYSIS_SCHEMA)

        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise GeminiAPIError(f"Gemini did not return valid JSON: {raw_text[:500]}") from exc

        suggestions: list[SuggestionDraft] = []
        if parsed.get("should_suggest_change"):
            proposed_changes: dict[str, Any] = {}
            if parsed.get("proposed_likelihood") is not None:
                proposed_changes["likelihood"] = parsed["proposed_likelihood"]
            if parsed.get("proposed_control_effectiveness") is not None:
                proposed_changes["control_effectiveness"] = parsed["proposed_control_effectiveness"]
            if proposed_changes:
                suggestions.append(
                    SuggestionDraft(
                        suggestion_type="assessment_change",
                        summary=parsed.get("suggestion_summary") or "Proposed assessment change",
                        rationale=parsed.get("suggestion_rationale") or "",
                        proposed_changes=proposed_changes,
                    )
                )

        return AIResponse(
            text=parsed.get("narrative", ""),
            model=self.model,
            latency_ms=latency_ms,
            suggestions=suggestions,
        )
