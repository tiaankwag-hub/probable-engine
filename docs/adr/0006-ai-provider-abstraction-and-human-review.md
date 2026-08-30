# ADR 0006: Provider-neutral AI abstraction with mandatory human review

## Status
Accepted

## Context
The brief mandates Gemini/Vertex AI in production, a mock provider for local development,
and — critically — that AI must never become an authoritative source for deterministic risk
scoring or silently overwrite authoritative data.

## Decision
- `packages/ai` defines an `AIProvider` interface (methods per capability: executive
  summary, risk analysis, control gap analysis, scenario commentary, etc.), implemented by
  `MockAIProvider` (deterministic templated output, no network calls) and
  `VertexGeminiProvider`.
- Every provider call is wrapped so its output is persisted to `ai_runs` and, where it
  implies a concrete change, to `ai_suggestions` with `human_review_status = pending`.
- The *only* code path that can change `risks`/`controls`/etc. from an AI suggestion is the
  standard authenticated risk-update API, invoked by a human "approve" action — there is no
  direct write path from `packages/ai` to authoritative tables.
- Deterministic scoring (`packages/risk_engine`) never calls `packages/ai` and vice versa;
  the two packages have no dependency on each other.

## Consequences
- Local development and CI never require Vertex AI credentials.
- Every AI-influenced change remains traceable to a specific model/prompt version and a
  named human approver, satisfying the audit requirement.
- Adding a future provider (e.g. a different model) is an additional `AIProvider`
  implementation, not a change to calling code.
