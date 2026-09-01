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

from packages.ai.provider import AIResponse, CandidateAssessment, SuggestionDraft

DEFAULT_MODEL = "gemini-3.6-flash"
API_BASE = "https://generativelanguage.googleapis.com/v1beta"
REQUEST_TIMEOUT_SECONDS = 30.0

EXECUTIVE_SUMMARY_PROMPT = """You are an experienced enterprise risk management specialist preparing a board-level executive briefing on the current risk register. Ground every specific figure in the facts given below — never invent a number that isn't given or directly derivable from them. Executives reading this want to know: what's going well, what isn't, where they need to focus first, whether the organization is trending in the right direction, and what to watch on the horizon — both inside the organization (its own control and process weaknesses) and outside it (market, regulatory, and threat-landscape factors implied by the categories most exposed below). You may use your own general risk-management judgment to frame the horizon-watch section, but say so explicitly rather than presenting judgment as fact.

Risk register snapshot:
- Total open risks: {total_risks}
- By band — Extreme: {extreme_count}, High: {high_count}, Moderate: {moderate_count}, Low: {low_count}, Unscored: {unscored_count}
- Category exposure: {category_exposure_block}
- Top risks by residual score:
{top_risks_block}

Governance and control health:
- Weak controls (effectiveness <= 2/5): {weak_controls_count}
- Overdue remediation actions: {overdue_actions_count}
- Overdue risk reviews: {overdue_reviews_count}

Risk appetite / tolerance position:
- {appetite_summary}
- Breach risks requiring attention: {breach_risk_titles}

Trend versus the last snapshot:
- {trend_summary}

Emerging Risk Radar (internal horizon-watch signal pipeline):
- {horizon_summary}

Write a board-ready executive summary of exactly 3 short paragraphs (roughly 150-220 words total):
1. Overall risk posture right now — the headline, what's good, what's bad.
2. Where leadership should focus first, and whether the organization's trajectory is improving, worsening, or stable — tie this explicitly to whether risks sit within, approaching, or outside stated appetite/tolerance.
3. What to watch on the horizon, both inside the organization and in the broader market/regulatory/threat environment — grounded in the categories most exposed and any active emerging-risk signals, noting plainly where you're applying general judgment rather than register data.

Separate the paragraphs with a blank line."""

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

CONTROL_GAP_PROMPT = """You are a controls analyst reviewing whether a risk has adequate mitigating controls. Base your analysis only on the facts given below — do not assume information that isn't provided.

Risk: {title}
Category: {category}
Current residual band: {residual_band}
Linked controls ({control_count}):
{controls_block}

Write a short (2-4 sentence) narrative on whether the linked controls appear adequate. Then decide
whether to suggest adding a new control — only if there is a concrete gap (no controls linked at
all, or every linked control is rated weak), never as a matter of routine. If you suggest one,
give it a short name, a one-sentence description, and pick the single most fitting control_type
from exactly: preventive, detective, corrective."""

CONTROL_GAP_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "narrative": {"type": "STRING"},
        "should_suggest_control": {"type": "BOOLEAN"},
        "control_name": {"type": "STRING", "nullable": True},
        "control_description": {"type": "STRING", "nullable": True},
        "control_type": {"type": "STRING", "nullable": True},
        "rationale": {"type": "STRING", "nullable": True},
    },
    "required": ["narrative", "should_suggest_control"],
}

EMERGING_RISK_PROMPT = """You are a risk analyst scanning a risk register for potential coverage gaps. Base your analysis only on the facts given below — do not invent statistics or assume information that isn't provided.

Current risk category coverage (category: number of registered risks):
{category_summary}

Existing risk titles already registered (do not propose anything that duplicates one of these):
{existing_titles}

Write a short (2-4 sentence) narrative on which category appears least covered relative to the
others. Then decide whether to propose exactly one new candidate risk for that category — only
propose one if you have a concrete, specific idea grounded in what a company with this category
mix would plausibly face, never a vague placeholder, and never a duplicate of an existing title.
If you propose one, give it a short title, a one-sentence risk statement, and the category name
(reuse one of the category names given above)."""

EMERGING_RISK_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "narrative": {"type": "STRING"},
        "should_propose_risk": {"type": "BOOLEAN"},
        "proposed_title": {"type": "STRING", "nullable": True},
        "proposed_statement": {"type": "STRING", "nullable": True},
        "proposed_category": {"type": "STRING", "nullable": True},
        "rationale": {"type": "STRING", "nullable": True},
    },
    "required": ["narrative", "should_propose_risk"],
}

MARKET_ANALYSIS_PROMPT = """You are a risk management analyst preparing brief market/industry context commentary for a board of directors. This prototype has no live market data feed connected — base your commentary only on your own general knowledge, and explicitly note in your answer that it reflects general knowledge rather than real-time market data. Be concise (3-5 sentences).

This organization's risk register category exposure (category: number of registered risks):
{category_summary}

Write commentary on industry/market trends relevant to the categories most represented above."""

SIGNAL_TRIAGE_PROMPT = """You are a risk analyst triaging one external signal (a news item or regulatory notice) for an organization's emerging-risk radar. Base your assessment only on the facts given below.

Signal content: {content}
Classified risk category: {classified_category}
Existing risks already registered in that category: {existing_titles_block}

Decide whether this signal is specific and relevant enough to propose as a new emerging-risk
candidate for this organization — only say yes if it describes a concrete, plausible risk that
isn't already obviously covered by an existing risk in that category. If yes, give it a short
title (a risk name, not a headline) and a one-to-two sentence risk-framed summary (what could
happen to this organization, not just what the signal reports), plus a one-sentence rationale
for why it's relevant now."""

SIGNAL_TRIAGE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "is_relevant": {"type": "BOOLEAN"},
        "title": {"type": "STRING", "nullable": True},
        "summary": {"type": "STRING", "nullable": True},
        "relevance_assessment": {"type": "STRING"},
    },
    "required": ["is_relevant", "relevance_assessment"],
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

    def analyze_control_gaps(self, context: dict[str, Any]) -> AIResponse:
        prompt = CONTROL_GAP_PROMPT.format(**context)
        raw_text, latency_ms = self._generate(prompt, response_schema=CONTROL_GAP_SCHEMA)

        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise GeminiAPIError(f"Gemini did not return valid JSON: {raw_text[:500]}") from exc

        suggestions: list[SuggestionDraft] = []
        if parsed.get("should_suggest_control") and parsed.get("control_name"):
            suggestions.append(
                SuggestionDraft(
                    suggestion_type="new_control",
                    summary=f"Add control: {parsed['control_name']}",
                    rationale=parsed.get("rationale") or "",
                    proposed_changes={
                        "name": parsed["control_name"],
                        "description": parsed.get("control_description") or "",
                        "control_type": (parsed.get("control_type") or "preventive").lower(),
                    },
                )
            )

        return AIResponse(
            text=parsed.get("narrative", ""),
            model=self.model,
            latency_ms=latency_ms,
            suggestions=suggestions,
        )

    def scan_emerging_risks(self, context: dict[str, Any]) -> AIResponse:
        prompt = EMERGING_RISK_PROMPT.format(**context)
        raw_text, latency_ms = self._generate(prompt, response_schema=EMERGING_RISK_SCHEMA)

        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise GeminiAPIError(f"Gemini did not return valid JSON: {raw_text[:500]}") from exc

        suggestions: list[SuggestionDraft] = []
        if parsed.get("should_propose_risk") and parsed.get("proposed_title"):
            suggestions.append(
                SuggestionDraft(
                    suggestion_type="new_risk",
                    summary=f"Consider adding: {parsed['proposed_title']}",
                    rationale=parsed.get("rationale") or "",
                    proposed_changes={
                        "title": parsed["proposed_title"],
                        "statement": parsed.get("proposed_statement") or "",
                        "category": parsed.get("proposed_category") or "",
                    },
                )
            )

        return AIResponse(
            text=parsed.get("narrative", ""),
            model=self.model,
            latency_ms=latency_ms,
            suggestions=suggestions,
        )

    def generate_market_analysis(self, context: dict[str, Any]) -> AIResponse:
        prompt = MARKET_ANALYSIS_PROMPT.format(**context)
        text, latency_ms = self._generate(prompt)
        return AIResponse(text=text.strip(), model=self.model, latency_ms=latency_ms)

    def analyze_signal(self, context: dict[str, Any]) -> CandidateAssessment:
        prompt = SIGNAL_TRIAGE_PROMPT.format(**context)
        raw_text, latency_ms = self._generate(prompt, response_schema=SIGNAL_TRIAGE_SCHEMA)

        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise GeminiAPIError(f"Gemini did not return valid JSON: {raw_text[:500]}") from exc

        return CandidateAssessment(
            is_relevant=bool(parsed.get("is_relevant")),
            title=parsed.get("title") or "",
            summary=parsed.get("summary") or "",
            relevance_assessment=parsed.get("relevance_assessment", ""),
            model=self.model,
            latency_ms=latency_ms,
        )
