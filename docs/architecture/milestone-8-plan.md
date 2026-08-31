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
- ~~No control-gap-analysis or scenario-commentary capability~~ — control-gap analysis was
  added in the same-day addendum below; scenario-commentary (AI narrative over a Monte Carlo
  scenario's results) remains unbuilt.
- **No prompt-injection-specific defenses beyond the allow-listed context builder** — the
  threat model's mitigation for this class of risk is precisely that a prompt is built from
  a small, explicit, hand-picked dict rather than free-text fields a user fully controls
  (e.g. a risk's `statement` is included, but nothing from it is ever used to construct a
  tool call or a write path) — no additional output-side filtering was added, since the only
  thing an AI response can ever produce is a `pending` suggestion a human must approve.
- Emerging Risk Radar (Milestone 9), MCP gateway (10), and GCP deployment hardening (11) are
  unchanged.

## Addendum: control-gap analysis, emerging-risk scan, market analysis

Same-day follow-up, in response to being asked directly what AI capabilities existed: the
original scope covered executive summaries and risk analysis only. Three more capabilities
were added to the same abstraction — no new architecture, just three more `AIProvider`
methods, three more prompt templates, and two new suggestion types flowing through the
existing human-review gate.

### What was built

- **Control-gap analysis** (`CONTROL_GAP_ANALYSIS`): per-risk, like risk analysis — reuses
  its exact ownership boundary (`REQUEST_OWN_AI_ANALYSIS`/`REQUEST_ANY_AI_ANALYSIS`, so a
  Risk Owner can request it for their own risk). Looks at a risk and its linked controls
  (name, type, design/operating effectiveness — allow-listed) and, only when there's a
  concrete gap (no controls linked at all, or every linked control is rated weak), suggests
  one new control. A new `suggestion_type = "new_control"` carries the proposed name,
  description, and control type; **approving it doesn't just flip a field — it creates a
  real `Control` row and links it to the risk**, through the same `control_service.py` the
  interactive "create control" API endpoint now also calls (extracted from that router so
  both paths stay identical, code-code and audit-event-for-audit-event).
- **Emerging-risk scan** (`EMERGING_RISK_SCAN`): portfolio-level, restricted to Risk
  Manager/Administrator (`REQUEST_EMERGING_RISK_SCAN`, new) rather than reusing the executive
  summary's wider audience — an approved suggestion here creates a brand-new `Risk`, a bigger
  action than a narrative. Compares real, computed risk-count-per-category across every
  taxonomy category (including ones with zero risks, which a dashboard's occupied-only
  category exposure list can't show) and, for whichever category is least covered, proposes
  exactly one candidate risk. A new `suggestion_type = "new_risk"` carries title, statement,
  and category — this is the one case where `AISuggestion.risk_id` is legitimately null (no
  risk exists yet to attach to), which required a migration making that column nullable.
  Approving it creates the risk via the ordinary `risk_service.create_risk()`, but
  **deliberately with a minimal, unrated placeholder assessment (likelihood 1, every impact
  dimension 1)** — the one thing this capability is never allowed to do is have the AI invent
  a real likelihood/impact score; a human must record the actual assessment afterward, and
  the risk's `latest_update` field says so explicitly.
- **Market analysis** (`MARKET_ANALYSIS`): portfolio-level, narrative only, never produces a
  suggestion — there's nothing here for a human to approve, only commentary. Its own
  permission (`REQUEST_MARKET_ANALYSIS`, granted like executive summary to Risk Manager,
  Executive, Administrator). This prototype has no external market/news data source, so the
  prompt is explicit that the model should answer from its own general knowledge and say so
  — and the UI repeats that caveat next to every response, so nobody mistakes general-purpose
  commentary for real market intelligence. The mock provider is equally honest: rather than
  fabricate plausible-looking "market insight" from a template (which would be actively
  misleading for this specific capability), it states outright that no live-data mock output
  is available and to configure a real provider.
- Frontend: the risk detail page's AI Analysis panel gained a second "Request control gap
  analysis" button running independently of "Request AI analysis" (separate poll state, one
  shared suggestion list, since both attach to the same risk); `/ai` gained Market Analysis
  and Emerging Risk Scan panels, the latter rendering any suggestion it produces inline via
  the same `SuggestionCard` the review queue uses, wired to refresh that queue on decision.
  Every suggestion card everywhere now shows an explicit type label (Assessment change / New
  control / New risk) rather than only a generic key→value dump.
- Seed data: `seed_demo_ai_content()` now seeds one run per capability (5 total). RSK-1004's
  one seeded control is deliberately weak (design 2, operating 1), so control-gap analysis
  produces a genuine pending suggestion the same way RSK-1002's seeded incident does for risk
  analysis — not a fabricated one.

### Tests

18 new `packages/ai` unit tests (mock + Gemini, all three new methods, each provider's
distinct branches), 6 new `apps/worker` job tests (dispatch + a real `new_control` produced
from a genuinely weak seeded control), 10 new `apps/api` integration tests (RBAC for all
three new endpoints, and — the two tests that actually prove the write paths work — approving
a `new_control` suggestion and confirming a real `Control` now appears in
`GET /risks/{id}/controls`, and approving a `new_risk` suggestion and confirming a real `Risk`
exists via `GET /risks?q=`, in `draft` status with `likelihood == 1`). **373 pytest tests, all
passing** (up from 340). Frontend re-verified clean via `npx tsc --noEmit` and `npm run
build`.

### Local demonstration, against the user's own real Gemini key

Verified live against the real `GeminiAPIProvider` (the user's own AI Studio key, already in
this environment's `.env`), not just the mock: the Market Analysis panel produced genuine,
grounded commentary on the portfolio's actual category mix, correctly labeled `model:
gemini-3.6-flash`; two separate Emerging Risk Scan requests each produced a distinct,
plausible new-risk candidate for "People & Culture" (the real least-covered category at the
time); and the seeded control-gap suggestion for RSK-1004, once approved, created a real
second `Control` ("Compensating Legal & Regulatory control for Upcoming data-residency
regulation") visibly linked in that risk's Controls panel — not a rendering-only change.

While verifying against the live key, one real, unrelated bug surfaced and was fixed: Google
had retired `gemini-2.0-flash` (the model this provider was hard-coded to by default) in
favor of `gemini-3.6-flash` sometime after this milestone's original code was written — every
call was failing with a 404 until `DEFAULT_MODEL` was updated and the two tests pinning the
old name were updated with it. Not caused by this addendum's changes, but caught in the
course of testing it.

### Explicitly still deferred

- **Scenario-commentary** (AI narrative over a Monte Carlo scenario's results) remains
  unbuilt — the last capability ADR 0006 named that hasn't been.
- **A risk can only get one `new_control` suggestion at a time reviewed independently per
  run** — nothing deduplicates a second control-gap analysis on the same still-uncontrolled
  risk from proposing another new control rather than noticing one is already pending;
  acceptable for a prototype, same as risk-analysis's pre-existing lack of suggestion
  deduplication.
- **Emerging-risk scan has no memory of risks it already proposed in a prior run** —
  `existing_titles` is passed to the real provider specifically to reduce this, but nothing
  stops a human from approving the same conceptual risk twice under slightly different
  wording across two separate scans.
