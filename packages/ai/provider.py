"""AI provider abstraction (Milestone 8, ADR 0006). Every provider
implements the same interface regardless of what's behind it — a
deterministic mock, Google's public Generative Language API (this
milestone's real implementation, callable with a personal AI Studio
key), or a future `VertexGeminiProvider` using Google Cloud's Vertex AI
SDK in production. Callers (`packages/shared/ai_service.py`) never know
or care which one is active; swapping providers is a one-line change to
`factory.get_provider()`, never a change to calling code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class SuggestionDraft:
    """A provider's proposed change, not yet persisted or reviewed. Only
    `packages/shared/ai_service.py` turns this into an `AISuggestion` row,
    and only a human "approve" action ever turns it into an actual change
    to `risks` — see ADR 0006."""

    suggestion_type: str
    summary: str
    rationale: str
    proposed_changes: dict[str, Any]


@dataclass(frozen=True)
class AIResponse:
    text: str
    model: str
    latency_ms: int
    suggestions: list[SuggestionDraft] = field(default_factory=list)


@dataclass(frozen=True)
class CandidateAssessment:
    """The Emerging Risk Radar's own structured output (Milestone 9) — not
    an `AIResponse`, since a signal triage doesn't produce a narrative +
    suggestions to review through `ai_suggestions`; it produces (or
    doesn't) an `EmergingRiskCandidate` directly. That candidate starts
    and can stay in a non-authoritative lifecycle state on its own — see
    `packages/shared/models/emerging_risk.py` — so this needs no separate
    approval step at the provider-response level; the review gate is the
    candidate's own lifecycle transition, made by a human."""

    is_relevant: bool
    title: str
    summary: str
    relevance_assessment: str
    model: str
    latency_ms: int


class AIProvider(Protocol):
    def generate_executive_summary(self, context: dict[str, Any]) -> AIResponse: ...

    def analyze_risk(self, context: dict[str, Any]) -> AIResponse: ...

    def analyze_control_gaps(self, context: dict[str, Any]) -> AIResponse: ...

    def scan_emerging_risks(self, context: dict[str, Any]) -> AIResponse: ...

    def generate_market_analysis(self, context: dict[str, Any]) -> AIResponse: ...

    def analyze_signal(self, context: dict[str, Any]) -> CandidateAssessment: ...
