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

from packages.ai.provider import AIResponse, CandidateAssessment, IntakeTurnResult, SuggestionDraft

DEFAULT_MODEL = "gemini-3.6-flash"
API_BASE = "https://generativelanguage.googleapis.com/v1beta"
REQUEST_TIMEOUT_SECONDS = 30.0

EXECUTIVE_SUMMARY_PROMPT = """You are an experienced enterprise risk management specialist preparing a board-level executive briefing. This is a SYNTHESIS, not a recount of register statistics — the platform has already run individual AI analyses across many risks and controls, and your job is to pull those findings together into the meta-picture: what patterns show up across multiple analyses, what's still sitting unactioned, and what that means for the organization as a whole. A reader who has already seen the dashboard numbers should still learn something new from you. Ground every specific figure and claim in the facts given below — never invent a number, a finding, or a risk name that isn't given or directly derivable from them.

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

What the platform's own AI risk-analysis and control-gap-analysis reviews have found, most recent first:
{recent_analyses_block}

AI-identified suggestions still awaiting a Risk Manager's decision:
{pending_suggestions_block}

Most recent AI market/industry commentary:
{market_analysis_excerpt}

Most recent AI emerging-risk category-coverage scan:
{emerging_scan_excerpt}

Emerging Risk Radar (internal horizon-watch signal pipeline):
- {horizon_summary}

You MUST write exactly 4 paragraphs, separated by a blank line, in exactly this order. Do not
merge, skip, or reorder any of them — an executive summary missing paragraph 2 below is
incomplete and unacceptable, even if that makes the summary longer than a typical briefing
(target 280-380 words total; go longer rather than drop a paragraph).

PARAGRAPH 1 — Overall risk posture right now: the headline, what's good, what's bad.

PARAGRAPH 2 — REQUIRED, do not omit: what the platform's own risk and control analyses have
already surfaced. This is the one paragraph a plain register readout cannot give you, so it must
reference at least one specific finding by risk name from the analyses listed above — never a
vague "several analyses found issues." Is there a recurring pattern across multiple findings
(e.g. more than one analysis turning up an untested control, or gaps concentrated in one
category)? Name it if there is one, and say plainly if the findings above are too few, or all
about the same risk, to support a pattern claim — that is itself useful information (it means
AI review coverage is still thin). State how many AI-identified suggestions are awaiting review
and name at least one.

PARAGRAPH 3 — Where leadership should focus first, and whether the organization's trajectory is
improving, worsening, or stable — tie this explicitly to whether risks sit within, approaching,
or outside stated appetite/tolerance.

PARAGRAPH 4 — What to watch on the horizon, both inside the organization and in the broader
market/regulatory/threat environment — draw on the market commentary and emerging-risk scan
above plus any active radar signals, adding your own general judgment only where it's clearly
labeled as such rather than presented as register fact.

Ground every specific figure and claim in the facts given above — never invent a number, a
finding, or a risk name that isn't given or directly derivable from them."""

RISK_ANALYSIS_PROMPT = """You are a senior risk analyst conducting a genuine review of one risk register entry — not a rubber stamp, an actual judgment on whether the current rating still reflects reality. Ground every claim in the facts given below; never invent or assume anything not provided.

Risk: {title}
Category: {category} | Department: {department}
Cause: {cause}
Event: {event}
Impact: {impact}
Statement: {statement}

Current assessment:
- Likelihood: {likelihood}/5, Overall impact: {overall_impact}, Inherent score: {inherent_score} ({inherent_band})
- Control effectiveness: {control_effectiveness}/5, Residual score: {residual_score} ({residual_band})
- Decision: {decision} | Velocity: {velocity} | Confidence: {confidence}
- Appetite position: {appetite_status}
- Versus the last assessment: {assessment_trend}

Mitigating controls ({control_count}):
{controls_block}

Recent incidents ({recent_incident_count}):
{incidents_block}

Open remediation actions ({overdue_action_count} overdue):
{open_actions_block}

Open issues:
{open_issues_block}

Write a genuine analyst-grade review — 2-3 short paragraphs, not a one-liner. Does the residual
score make sense given the actual control landscape and test history above, not just the
numbers on file? Do the recent incidents, a failed or overdue control test, or overdue actions
suggest the current rating is stale? Is there one specific driver of exposure worth naming — a
weak or untested control, a pattern across incidents, a control gap the test findings expose?
Then decide whether the facts justify suggesting a change to the likelihood or control
effectiveness rating — only suggest one if there's a concrete reason above (a real incident, a
failed control test, a critical overdue action), never as a matter of routine. If you suggest a
change, give a one-sentence summary and a rationale that names the specific fact driving it."""

RISK_ANALYSIS_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "narrative": {"type": "STRING"},
        "should_suggest_change": {"type": "BOOLEAN"},
        "suggestion_summary": {"type": "STRING", "nullable": True},
        "suggestion_rationale": {"type": "STRING", "nullable": True},
        "proposed_likelihood": {"type": "INTEGER", "nullable": True},
        "proposed_control_effectiveness": {"type": "INTEGER", "nullable": True},
    },
    # suggestion_summary/suggestion_rationale are marked required (though
    # nullable) so the model must explicitly decide null vs. real text
    # rather than silently omitting the key — an omitted-but-optional
    # rationale was observed to reach the UI empty even when
    # should_suggest_change was true and the narrative clearly reasoned
    # about why.
    "required": ["narrative", "should_suggest_change", "suggestion_summary", "suggestion_rationale"],
}

CONTROL_GAP_PROMPT = """You are a controls analyst reviewing whether a risk has adequate mitigating controls — a real assessment of design and operating effectiveness against what the risk actually needs, not a headcount of controls. Base your analysis only on the facts given below — do not assume information that isn't provided.

Risk: {title}
Category: {category}
Cause: {cause}
Event: {event}
Impact: {impact}
Statement: {statement}
Residual score: {residual_score} ({residual_band})

Linked controls ({control_count}):
{controls_block}

Write a genuine controls review (2-3 short paragraphs, not a one-liner): given what could
actually go wrong (the cause/event/impact above), do the linked controls cover it — do they
address the cause (preventive), detect the event (detective), or limit the impact
(corrective)? Weigh the actual test findings and dates above, not just the design/operating
numbers — a control rated 4/5 that hasn't been tested in over a year, or whose last test found
a problem, is not the same as one recently confirmed effective. Then decide whether to suggest
adding a new control — only if there is a concrete gap (no controls linked at all, every linked
control rated weak, a control type missing entirely for how this risk could materialize, or a
test finding exposing a real weakness), never as a matter of routine. If you suggest one, give
it a short name, a one-sentence description grounded in the specific gap you found, and pick
the single most fitting control_type from exactly: preventive, detective, corrective."""

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
    "required": [
        "narrative", "should_suggest_control", "control_name", "control_description",
        "control_type", "rationale",
    ],
}

EMERGING_RISK_PROMPT = """You are an experienced risk analyst scanning a risk register for coverage gaps — categories where the organization plausibly faces exposure that hasn't been identified, not just categories with a low headcount. Base your analysis only on the facts given below — do not invent statistics or assume information that isn't provided.

Current risk category coverage (category: risk count, average residual score):
{category_summary}

Existing risk titles already registered (do not propose anything that duplicates one of these):
{existing_titles}

Write a genuine analyst judgment (2-3 sentences) on which category looks most under-identified —
weigh both the count AND the average severity: a category with few risks that are also low
severity is a stronger signal of under-identification than one with few risks that are already
rated severely (which may just mean the category is genuinely lower-risk for this
organization). Then decide whether to propose exactly one new candidate risk for that category —
only propose one if you have a concrete, specific idea grounded in what a company with this
category mix would plausibly face, never a vague placeholder, and never a duplicate of an
existing title. If you propose one, give it a short title, a one-to-two sentence risk statement
naming a plausible cause and consequence (not just a category label), and the category name
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
    "required": [
        "narrative", "should_propose_risk", "proposed_title", "proposed_statement",
        "proposed_category", "rationale",
    ],
}

MARKET_ANALYSIS_PROMPT = """You are a risk management analyst preparing market/industry context commentary for a board of directors. This prototype has no live market data feed connected — base your commentary only on your own general knowledge, and explicitly note in your answer that it reflects general knowledge rather than real-time data.

This organization's risk register category exposure (category: risk count, average residual score):
{category_summary}

Its top risks by residual score right now:
{top_risks_block}

Write 2-3 short paragraphs of commentary that actually engages with this organization's specific
exposure, not a generic industry overview: for the one or two categories most represented (by
count and severity together), name concrete, current market/regulatory/competitive/
threat-landscape dynamics a company with this exposure should be watching, and where relevant
connect them to the specific top risks listed above rather than the category label alone. Be
specific enough to be useful to a board deciding where to focus, while being explicit that this
is general judgment, not a live feed."""

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
    "required": ["is_relevant", "relevance_assessment", "title", "summary"],
}


INTAKE_TURN_PROMPT = """You are a friendly risk-intake assistant helping a colleague who is not a risk-management expert describe a concern in their own words, so it can be logged as a DRAFT in the risk register for a Risk Manager to review and score properly. You are never assessing likelihood, impact, or severity — a human does that later. Never use risk-management jargon.

You need to end up knowing, in the person's own words (cleaned up, not verbatim):
- event: what could go wrong / what they've noticed
- impact: what it would affect or cost if it happened
- cause: why this could happen
- department_guess: which part of the business this mainly affects
- category_guess: your best-fit guess from exactly these categories: {category_names_block}
- title: a short name for it

Known so far: {draft_fields_block}

Conversation so far:
{transcript_block}

Their latest answer: {latest_user_message}

This is exchange {turn_number} of a target of about {max_turns}. Decide: do you now have enough for at least event, impact, and a category guess? If yes, set is_ready to true and write a short, warm reply_message summarizing what you understood in plain language, asking them to confirm or correct anything before it's submitted. If no, set is_ready to false and ask exactly ONE short, simple follow-up question in reply_message about the single most important missing piece — never ask more than one question at a time, never ask about a numeric score.

Only include a field below if you now know it from what they've actually said — never invent or assume one."""

INTAKE_TURN_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "reply_message": {"type": "STRING"},
        "is_ready": {"type": "BOOLEAN"},
        "event": {"type": "STRING", "nullable": True},
        "impact": {"type": "STRING", "nullable": True},
        "cause": {"type": "STRING", "nullable": True},
        "department_guess": {"type": "STRING", "nullable": True},
        "category_guess": {"type": "STRING", "nullable": True},
        "title": {"type": "STRING", "nullable": True},
    },
    "required": ["reply_message", "is_ready"],
}

_INTAKE_FIELD_KEYS = ("event", "impact", "cause", "department_guess", "category_guess", "title")


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

        narrative = parsed.get("narrative", "")
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
                        # A model can emit an empty rationale despite the
                        # schema asking for one — fall back to the
                        # narrative itself rather than show a blank
                        # "why" on the suggestion card.
                        rationale=parsed.get("suggestion_rationale") or narrative or "",
                        proposed_changes=proposed_changes,
                    )
                )

        return AIResponse(
            text=narrative,
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

        narrative = parsed.get("narrative", "")
        suggestions: list[SuggestionDraft] = []
        if parsed.get("should_suggest_control") and parsed.get("control_name"):
            suggestions.append(
                SuggestionDraft(
                    suggestion_type="new_control",
                    summary=f"Add control: {parsed['control_name']}",
                    rationale=parsed.get("rationale") or narrative or "",
                    proposed_changes={
                        "name": parsed["control_name"],
                        "description": parsed.get("control_description") or "",
                        "control_type": (parsed.get("control_type") or "preventive").lower(),
                    },
                )
            )

        return AIResponse(
            text=narrative,
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

        narrative = parsed.get("narrative", "")
        suggestions: list[SuggestionDraft] = []
        if parsed.get("should_propose_risk") and parsed.get("proposed_title"):
            suggestions.append(
                SuggestionDraft(
                    suggestion_type="new_risk",
                    summary=f"Consider adding: {parsed['proposed_title']}",
                    rationale=parsed.get("rationale") or narrative or "",
                    proposed_changes={
                        "title": parsed["proposed_title"],
                        "statement": parsed.get("proposed_statement") or "",
                        "category": parsed.get("proposed_category") or "",
                    },
                )
            )

        return AIResponse(
            text=narrative,
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

    def continue_risk_intake(self, context: dict[str, Any]) -> IntakeTurnResult:
        prompt = INTAKE_TURN_PROMPT.format(**context)
        raw_text, latency_ms = self._generate(prompt, response_schema=INTAKE_TURN_SCHEMA)

        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise GeminiAPIError(f"Gemini did not return valid JSON: {raw_text[:500]}") from exc

        updated_fields = {k: parsed[k] for k in _INTAKE_FIELD_KEYS if parsed.get(k)}
        return IntakeTurnResult(
            reply_message=parsed.get("reply_message") or "",
            updated_fields=updated_fields,
            is_ready_to_submit=bool(parsed.get("is_ready")),
            model=self.model,
            latency_ms=latency_ms,
        )
