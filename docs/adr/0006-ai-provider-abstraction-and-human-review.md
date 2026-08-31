# ADR 0006: Provider-neutral AI abstraction with mandatory human review

## Status
Accepted

## Context
The brief mandates Gemini/Vertex AI in production, a mock provider for local development,
and — critically — that AI must never become an authoritative source for deterministic risk
scoring or silently overwrite authoritative data.

## Decision
- `packages/ai` defines an `AIProvider` interface (methods per capability: executive summary,
  risk analysis, control-gap analysis, emerging-risk scan, and market analysis today;
  scenario commentary is named as a future capability of the same shape), implemented by
  `MockAIProvider` (deterministic templated output, no network calls) and, as built in
  Milestone 8, `GeminiAPIProvider` —
  which calls Google's public Generative Language API directly using a personal Google AI
  Studio API key (`GEMINI_API_KEY`), not Vertex AI. This was a deliberate substitution for
  the prototype phase: the user does not yet have Vertex AI access from this environment,
  but does have a personal Gemini API key, and needed the AI feature "fully functional in
  the prototype," not mocked. `packages/ai/factory.py`'s `get_provider()` is the single swap
  point — it returns `GeminiAPIProvider()` when `GEMINI_API_KEY` is set, else
  `MockAIProvider()`. `VertexGeminiProvider` (the company's actual GCP provider, using the
  `google-cloud-aiplatform` SDK's service-account auth instead of an API-key query param)
  remains a documented, not-yet-built future implementation of the exact same `AIProvider`
  protocol — swapping to it on GCP deployment means adding that one class and one branch to
  `get_provider()`, with zero changes to `packages/shared/ai_service.py`, the API router, or
  the worker job, all of which depend only on the `AIProvider` protocol.
- Every provider call is wrapped so its output is persisted to `ai_runs` and, where it
  implies a concrete change, to `ai_suggestions` with `human_review_status = pending`.
- The *only* code path that can change `risks`/`controls`/etc. from an AI suggestion is a
  human "approve" action routed through the same service-layer function the interactive UI
  itself uses for that entity — `risk_service.update_risk` for an `assessment_change`
  suggestion, `control_service.create_control` for a `new_control` suggestion,
  `risk_service.create_risk` for a `new_risk` suggestion. There is no direct write path from
  `packages/ai` to authoritative tables. A `new_risk` suggestion is never allowed to assign a
  real likelihood/impact score itself — approving one creates the risk with a deliberately
  minimal, unrated placeholder assessment, so a human still performs the actual assessment.
- Deterministic scoring (`packages/risk_engine`) never calls `packages/ai` and vice versa;
  the two packages have no dependency on each other.
- The Gemini API key lives only in a local, gitignored `.env` file, read via environment
  variable at process start — it is never logged, never persisted to the database, and never
  appears in any file committed to the repository (`.env.example` ships a blank placeholder
  with a comment pointing to where to obtain one).

## Consequences
- Local development and CI never require Gemini or Vertex AI credentials — the seed script
  always uses `MockAIProvider` directly regardless of what's in the environment, so seed
  output stays deterministic.
- Every AI-influenced change remains traceable to a specific model/prompt version and a
  named human approver, satisfying the audit requirement.
- Adding a future provider (e.g. `VertexGeminiProvider`, or a different model entirely) is
  an additional `AIProvider` implementation plus one branch in `get_provider()`, not a
  change to calling code — demonstrated in practice by Milestone 8 itself, which added
  `GeminiAPIProvider` alongside the pre-existing `MockAIProvider` with no changes needed to
  the service layer, API router, or worker job.
