# Milestone 8 Implementation Plan — COMPLETE

AI provider integration: a provider-neutral abstraction (ADR 0006) with two concrete
providers today — a deterministic mock for local dev/CI, and a real, network-calling Google
Gemini provider so the prototype is genuinely functional, not a stub. The user's stated
constraint drove the design: this will move to their company's Vertex AI/Gemini provider on
GCP, so swapping providers must be a one-file change, never a rewrite of calling code.

## What was built

### `packages/ai` (new package) — the provider abstraction, zero dependency on `packages/risk_engine`
- **`provider.py`**: `AIProvider` is a `Protocol` with two capability methods —
  `generate_executive_summary(context)` and `analyze_risk(context)` — returning a shared
  `AIResponse` (text, model name, latency, structured `suggestions`). This is the only
  surface any caller (the service layer, the worker job) ever depends on.
- **`mock_provider.py`**: `MockAIProvider` — deterministic templated logic, no network,
  no credentials. Suggests raising likelihood when a risk has recent incidents, suggests
  lowering control effectiveness when it has overdue actions, or makes no suggestion — the
  same three-branch logic every seed run and every CI test exercises identically.
- **`gemini_provider.py`**: `GeminiAPIProvider` — calls Google's public Generative Language
  API (`generativelanguage.googleapis.com`) directly over `httpx`, using
  `responseMimeType: application/json` plus an explicit `responseSchema` so risk-analysis
  output is always structured JSON, never free-text that needs fragile parsing. Reads
  `GEMINI_API_KEY`/`GEMINI_MODEL` from the environment; raises immediately if no key is
  configured rather than silently falling back.
- **`factory.py`**: `get_provider()` — returns `GeminiAPIProvider()` if `GEMINI_API_KEY` is
  set, else `MockAIProvider()`. This is the entire swap point. Deploying to GCP with the
  company's Vertex/Gemini provider means adding one more `AIProvider` implementation
  (`VertexGeminiProvider`, using the `google-cloud-aiplatform` SDK's service-account auth
  instead of an API-key query param) and one more branch here — no change to
  `packages/shared/ai_service.py`, the API router, or the worker job, since all three only
  ever see the `AIProvider` protocol.

### Database (PostgreSQL + Alembic)
New migration adds `ai_runs` (capability, model, prompt_version, requester, the exact risk
IDs and data sources fed into the prompt, raw response, latency, status/error, timestamps)
and `ai_suggestions` (one row per proposed change: type, summary, rationale, the proposed
field changes as JSON, and a `human_review_status` that starts and stays `pending` until a
human explicitly approves or rejects it). Every provider call is persisted here regardless
of outcome — this is what makes "AI never silently changes a risk" an auditable fact, not
just a promise in a doc.

### Backend
- **`packages/shared/ai_service.py`**: the bridge between the provider abstraction and the
  database, mirroring the `simulation_service.py`/`report_generate.py` split from prior
  milestones. Two context builders — `build_executive_summary_context` (reuses the
  Milestone 2 dashboard aggregation) and `build_risk_analysis_context` — construct
  hand-picked, allow-listed dicts (title, statement, category, likelihood,
  control_effectiveness, residual band, recent incident count, overdue action count) that
  become the prompt. Per the threat model, a full ORM object is never serialized into a
  prompt — only fields explicitly listed here ever reach the provider, so adding a new
  column to `Risk` cannot silently leak into an AI prompt. `create_pending_run` writes the
  initial row; `execute_executive_summary`/`execute_risk_analysis` call the provider and
  fill it in, creating `AISuggestion` rows for anything proposed. `approve_suggestion`
  applies a suggestion by reconstructing a full `AssessmentInput` — proposed fields from the
  suggestion, everything else read from the risk's current `latest_assessment` — and routing
  it through the ordinary `risk_service.update_risk()`, so an AI-originated change gets
  exactly the same versioning and audit trail as a human-typed one. There is no other write
  path from this module to `risks`.
- **AI API** (`apps/api/app/routers/ai.py`): `POST /ai/executive-summary`,
  `POST /ai/risk-analysis`, `GET /ai/runs/{id}` for polling, `GET /ai/suggestions` (risk-
  scoped for an owner checking their own risk, or unscoped with `?status=pending` for the
  review queue), and `POST /ai/suggestions/{id}/approve|reject`. All slow provider calls are
  dispatched through the existing JobQueue (ADR 0005) exactly like reports and simulations —
  a request returns a `pending` run immediately, the worker fills it in.
- **`apps/worker/app/jobs/ai_run.py`**: loads the run, marks it `running`, dispatches to
  executive-summary or risk-analysis execution based on `run.capability`, marks it `failed`
  with the error message on any exception (including a real Gemini API error) before
  re-raising.
- **RBAC**, following the existing Own/Any split (`RUN_OWN_SIMULATION`/`RUN_ANY_SIMULATION`
  precedent): `REQUEST_OWN_AI_ANALYSIS` (Risk Owner, their own risks), `REQUEST_ANY_AI_ANALYSIS`
  (Risk Manager, Administrator), `REQUEST_EXECUTIVE_SUMMARY` (Risk Manager, Executive,
  Administrator), `APPROVE_AI_SUGGESTIONS` (Risk Manager, Administrator only — an Executive
  can request and read a summary but never approve a change to a risk).

### Frontend
- **`/ai`** (AI Insights): an Executive Summary panel (poll-to-complete, narrative text with
  an explicit "AI-generated" / model-name label) and a Pending AI Suggestions review queue
  for Risk Managers/Administrators, with inline Approve/Reject.
- **Risk detail page**: an "AI Analysis" panel showing that risk's own suggestions —
  including any seeded or previously-requested ones, not just ones requested in the current
  browser session (see Bugs below) — plus a "Request AI analysis" button gated to the risk's
  owner, Risk Manager, or Administrator.

### Seed data
`database/seed/seed.py` gained `seed_demo_ai_content()`, following the established
per-entity-idempotency pattern. It targets `RSK-1002` (which already has a seeded incident
from Milestone 4), constructs an executive-summary run and a risk-analysis run, and — since
that risk has a recorded incident — persists exactly one pending suggestion ("increase
likelihood to 4"), so both the `/ai` review queue and the risk's own detail page have real
content immediately after `docker compose up`, no user action required. **Always uses
`MockAIProvider()` directly, regardless of whether `GEMINI_API_KEY` happens to be set** in
the environment running the seed script — per ADR 0006, local dev and CI must never require
real credentials, and seed output must stay deterministic across machines.

## Tests

- `packages/ai` unit tests: `MockAIProvider`'s three-branch suggestion logic, and
  `GeminiAPIProvider` against `httpx.MockTransport` (a fake HTTP layer) covering a
  successful structured response, a suggestion-free response, and the provider's own error
  handling on a non-200 response — no test ever makes a live network call.
- `apps/worker` job tests: executive-summary run end-to-end, risk-analysis run with no
  suggestion (no incidents/overdue actions), risk-analysis run that does produce a
  suggestion (via a seeded incident), and a run against a missing risk failing cleanly.
- `apps/api` integration tests: RBAC for both request endpoints (ownership enforcement
  identical in shape to simulations), run lifecycle and polling, the full approve flow
  (asserts the risk's likelihood, version, and history all update correctly), reject leaving
  the risk untouched, double-review rejected with 409, the pending queue restricted to
  approvers, and a risk owner able to see their own risk's suggestions without the
  unscoped-queue permission.
- Seed-script regression tests: creates the expected run/suggestion counts, fully idempotent
  on rerun, and correctly returns `False`/creates nothing when the target risk doesn't exist
  yet (matching the idempotency contract established for every other seed function).

**340 pytest tests, all passing** (up from 300). Frontend verified via `npx tsc --noEmit` and
`npm run build` (both clean, `/ai` present in the route manifest), plus a full live-stack
Playwright pass against a real Gemini API call using the user's personal AI Studio key
(confirmed working, then used only for interactive manual testing — all committed automated
tests use the mock provider or a fake HTTP transport) and against the mock provider: seeded
suggestion visible and approvable both from the global `/ai` review queue and from the
risk's own detail page, executive summary generation polling from Pending to Succeeded, and
reject leaving a risk's assessment unchanged.

## Bugs found and fixed during verification

- **A risk's own detail page didn't show its existing AI suggestions.** The original
  `RiskAiAnalysisPanel` only rendered suggestions attached to a `run` created by clicking
  "Request AI analysis" within that same browser session — so RSK-1002's seeded pending
  suggestion was correctly visible on the global `/ai` review queue but invisible on
  RSK-1002's own detail page, the first place a risk owner would actually look. This broke
  the "seeded data is visible immediately, no user action required" principle every prior
  milestone's seed data upheld. Caught by a live Playwright screenshot, not by any unit or
  API test (`GET /ai/suggestions?risk_id=` was already correctly tested in isolation — the
  bug was purely in what the component chose to fetch). Fixed by giving the panel its own
  persistent `suggestions` state, loaded via `GET /ai/suggestions?risk_id=` on mount and
  refreshed after any run completes or any approve/reject decision, rather than deriving
  suggestions solely from the transient in-session `run` state.
- **Approving a suggestion from the risk detail page didn't refresh the rest of that page.**
  Once the panel above was fixed and correctly displaying suggestions from any source, a
  second Playwright pass caught that clicking Approve updated the suggestion's own card
  (now showing "Approved") but left the page's Assessment section, inherent/residual scores,
  and History panel stale at their pre-approval values until a manual reload — a real
  inconsistency, since the risk's likelihood, version, and history entry had all genuinely
  changed on the backend (confirmed via a direct API call showing `likelihood: 4, version:
  2`, but the same values still `3`/`v1` on screen). The page's other mutations
  (`handleReassess`, action/control/issue/incident creation) all call the parent page's own
  `load()` after a successful change; the AI panel was the one exception, added later and
  self-contained, that never wired up to it. Fixed by adding an `onRiskChanged` callback
  prop, invoked only on a successful approve (a reject never changes the risk), wired to the
  parent's existing `load()` function — confirmed by re-running the same Playwright script,
  which now shows Likelihood 4, the recalculated inherent/residual scores, and a new `v2`
  History entry attributed to the approving Risk Manager immediately after the click.

## Explicitly still deferred

- **`VertexGeminiProvider` itself is not built** — this was scoped as a future GCP-side
  change, not part of this milestone. `factory.py` is the documented, single-file swap
  point: implement the same `AIProvider` protocol using the `google-cloud-aiplatform` SDK's
  service-account auth against the company's Vertex AI project, add a branch to
  `get_provider()` favoring it when running in that environment, and nothing else in this
  codebase changes.
- **No control-gap-analysis or scenario-commentary capability** — ADR 0006 names these as
  future capabilities of the same abstraction; only executive summary and risk analysis were
  built, matching what the brief actually asked for at this milestone.
- **No prompt-injection-specific defenses beyond the allow-listed context builder** — the
  threat model's mitigation for this class of risk is precisely that a prompt is built from
  a small, explicit, hand-picked dict rather than free-text fields a user fully controls
  (e.g. a risk's `statement` is included, but nothing from it is ever used to construct a
  tool call or a write path) — no additional output-side filtering was added, since the only
  thing an AI response can ever produce is a `pending` suggestion a human must approve.
- Emerging Risk Radar (Milestone 9), MCP gateway (10), and GCP deployment hardening (11) are
  unchanged.
