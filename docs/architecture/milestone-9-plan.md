# Milestone 9 Implementation Plan — COMPLETE

Emerging Risk Radar: signal adapters (fixtures first, per the roadmap), a deterministic
taxonomy classifier, an AI triage capability that turns a classified signal into a candidate,
and a human-only lifecycle that can accept a candidate into a real risk, link it to one
already on file, or dismiss it. Nothing here is authoritative until a human moves it there.

## What was built

### `packages/emerging_risk` (new package) — pure logic, no database dependency
- **`signals.py`**: `RawSignal` dataclass, a `SignalAdapter` protocol, and two deterministic
  fixture adapters (`FixtureNewsAdapter`, `FixtureRegulatoryAdapter`) standing in for a real
  external feed this prototype has no live connection to — matching the roadmap's "signal
  adapters (fixtures first)" phrasing exactly. Swapping in a real adapter later (an actual
  news API, a regulator's feed) means adding one more class with the same
  `fetch() -> list[RawSignal]` shape, mirroring the `AIProvider` swap-point pattern from
  Milestone 8.
- **`classification.py`**: a pure keyword-based classifier mapping a signal's text to one of
  the organization's existing risk categories — deliberately simple and fully explainable, no
  NLP/ML dependency, matching `packages/risk_engine` and `packages/simulations`'s own
  stdlib-only approach to "don't reach for a library this scale doesn't need." Every one of
  the 5 fixture signals classifies to a distinct, sensible category, verified directly.

### Database (PostgreSQL + Alembic)
New migration adds `emerging_signals` (source adapter, source citation — unique, so
re-ingestion never duplicates a real-world item — raw content, classification, ingested_at),
`emerging_risk_candidates` (title, summary, category_id, relevance_assessment, model,
lifecycle_status, matched_risk_id, created_risk_id, reviewed_by_id, reviewed_at), and
`emerging_candidate_signals` (many-to-many junction, since a candidate can be derived from
more than one signal per the domain model). `lifecycle_status` is a Postgres enum:
`candidate` → `under_review` → `accepted` / `linked_to_existing` / `dismissed`.

### A 6th `AIProvider` capability: `analyze_signal`
Not built as another `AIResponse`/`ai_suggestions` capability like Milestone 8's five —
this one produces a new `CandidateAssessment` dataclass (`is_relevant`, `title`, `summary`,
`relevance_assessment`, `model`, `latency_ms`) because a signal triage doesn't produce a
narrative-plus-suggestion for `ai_suggestions` to review; it produces (or doesn't) an
`EmergingRiskCandidate` directly, which is itself already a non-authoritative row sitting in
`candidate` state — the review gate is the candidate's own lifecycle transition, not a
separate approval step. `MockAIProvider` is deterministic (relevant whenever the signal
classified successfully; derives a title from the signal's own first sentence);
`GeminiAPIProvider` uses the same structured-JSON-schema pattern as every other capability.

### `packages/shared/emerging_risk_service.py`
- **`ingest_signals`**: fetches from every adapter, classifies each against the categories
  that actually exist right now, and persists only the ones not already seen (deduped by
  `source_citation` — a URL is the same real-world item no matter how many times ingestion
  runs). Returns only the newly created rows, matching this codebase's "return value means
  something was actually created" convention for idempotent functions.
- **`triage_signal`**: builds an allow-listed context (the signal's content, its classified
  category, and — scoped to just that category — the titles of risks already registered
  there, never full statements or the whole register) and calls `analyze_signal`. Creates a
  `candidate`-state `EmergingRiskCandidate` only if the provider judged it relevant.
- **`transition_candidate`**: the only path (besides linking) that can move a candidate to
  `under_review`, `accepted`, or `dismissed`. `accepted` creates a real `Risk` via the
  ordinary `risk_service.create_risk`, always with a deliberately minimal, unrated placeholder
  assessment (likelihood 1, every impact dimension 1) — the AI never assigns a real score,
  the same guarantee ADR 0006 makes for an approved `new_risk` AI suggestion in Milestone 8.
  Rejects moving to `linked_to_existing` directly (that's `link_candidate_to_existing_risk`'s
  job) or back to `candidate`, and rejects any transition once a candidate has already reached
  a terminal state.
- **`link_candidate_to_existing_risk`**: sets `matched_risk_id`, moves to `linked_to_existing`,
  same terminal-state guard.
- Both terminal-transition functions record their own `audit_events` row (entity
  `emerging_risk_candidate`), on top of whatever `create_risk` itself logs for the risk it
  creates.

### Backend
- **`apps/worker/app/jobs/emerging_signal_ingest.py`**: ingests, then triages every newly
  created signal, following the JobQueue pattern (ADR 0005) like every other slow/AI-touching
  action in this system. No dedicated "ingestion run" entity exists in the domain model — its
  outcome is observable through the rows it writes and through the generic `BackgroundJob`
  status `GET /api/v1/jobs/{id}` already exposes for polling (an existing endpoint from an
  earlier milestone, reused as-is).
- **Emerging risks API** (`apps/api/app/routers/emerging_risks.py`): `POST /ingest` (202,
  enqueues the job — not in the original API design doc's abbreviated Emerging risks section,
  added the same way Milestone 8 added capabilities beyond its own original list),
  `GET /emerging-risks` (filterable by `lifecycle_status`), `GET /emerging-risks/{id}`,
  `PATCH /emerging-risks/{id}` (lifecycle transition), `POST /emerging-risks/{id}/link-existing-risk`
  — matching the API design doc's four documented routes exactly, plus the one deviation.
- **RBAC**: `VIEW_EMERGING_RISKS` (Risk Owner, Risk Manager, Executive, Administrator —
  mirrors `VIEW_SIMULATION_RESULTS`'s audience exactly), `INGEST_EMERGING_SIGNALS` and
  `REVIEW_EMERGING_RISKS` (Risk Manager, Administrator only, matching the API design doc's
  matrix row "Review emerging-risk candidates" exactly). Distinct from Milestone 8's
  `REQUEST_EMERGING_RISK_SCAN` permission — that's a different capability (an AI-driven scan
  that directly proposes a new risk from category coverage counts, no signal or human-review
  candidate stage involved); this is the signal-ingestion pipeline.

### Frontend
- **`/emerging-risks`**: an "Ingest new signals" button (Risk Manager/Administrator) that
  polls the generic job endpoint until it succeeds, then reloads; a lifecycle-status filter
  bar; and a card per candidate showing its title, category, AI relevance assessment, summary,
  its source signal(s) (adapter name + a link to the citation, collapsed by default), and —
  for reviewers, only while the candidate is still `candidate`/`under_review` — action buttons
  for every valid transition (Mark Under Review, Accept as Emerging Risk, Link to Existing
  Risk with an inline risk-picker dropdown mirroring the Scenarios page's own "link a risk"
  UI, Dismiss). An accepted candidate shows a link straight to the risk it created; a linked
  one shows a link to the risk it matched.
- Nav link added between AI Insights and Import Wizard.

### Seed data
`seed_demo_emerging_risk_content()` ingests the fixture adapters and triages every resulting
signal via `MockAIProvider` (never the configured provider, matching ADR 0006's "local
dev/CI never requires credentials" guarantee), then deliberately walks the first three
candidates through `accepted`, `dismissed`, and `under_review` so `/emerging-risks` shows
every lifecycle outcome immediately — not just a pile of identical pending candidates. The
remaining two stay in `candidate` state, ready to demonstrate the review actions themselves.

## Tests

- 12 `packages/emerging_risk` unit tests: fixture adapters are deterministic and every
  citation is unique, classification is correct and deterministic for representative content
  in every seeded category, restricting to a known-category subset works, and no keyword
  match returns `None` rather than guessing.
- 8 new `packages/ai` unit tests (mock + Gemini) for `analyze_signal`: unclassified signals
  are never relevant, a classified one derives a sensible title from its own content, an
  existing-risk count is noted honestly, and Gemini's structured response is parsed correctly
  including the not-relevant and invalid-JSON paths.
- 3 `apps/worker` job tests: a full ingest-and-triage run against real seeded categories,
  idempotency on rerun (no duplicate signals), and the edge case of ingesting against zero
  known categories (every signal ends up unclassified, zero candidates — proves classification
  correctly refuses to invent a category that doesn't exist rather than guessing one).
- 15 `apps/api` integration tests: RBAC for ingest/view/review split exactly along the three
  new permissions, lifecycle-status filtering, and — the tests that actually prove the write
  paths work — accepting a candidate and confirming a real `Risk` exists in `draft` status
  with `likelihood == 1`, dismissing one and confirming no risk was created, rejecting a second
  transition on an already-finalized candidate with 409, rejecting a direct
  `linked_to_existing` PATCH with 400, and linking to an existing risk end-to-end.
- 3 seed-script regression tests: correct signal/candidate counts with the right lifecycle
  distribution, full idempotency on rerun, and correctly creating nothing when no users are
  seeded yet (matching the idempotency contract every other seed function in this file
  follows).

**413 pytest tests, all passing** (up from 373). Frontend verified via `npx tsc --noEmit` and
`npm run build` (both clean, `/emerging-risks` present in the route manifest), plus a full
live-stack Playwright pass: loaded the page and saw all 5 seeded candidates rendered with the
correct lifecycle-appropriate actions and labels (matching the exact distribution the seed
function produces), filtered to "Candidate", clicked "Accept as Emerging Risk" on one, and
confirmed via a direct API call that a real `Risk` (draft, unrated, likelihood 1) now existed
and the candidate's card updated in place to show "Created risk: view risk".

## Explicitly still deferred

- **Real signal adapters** — only the two fixture adapters exist; a genuine news API or
  regulatory-feed integration is future work, following the documented one-class swap point.
- **No de-duplication across separate triage runs at the candidate level** — `existing_titles`
  is passed to the real provider specifically to reduce a duplicate proposal, but nothing
  stops two different signals (or the same signal re-classified after a taxonomy change) from
  producing two candidates describing essentially the same underlying risk. A human reviewer
  is the actual de-duplication mechanism here, same limitation already accepted for Milestone
  8's emerging-risk-scan capability.
- **No scheduled/automatic ingestion** — `POST /ingest` is a manual trigger; a real Cloud
  Scheduler-driven periodic ingestion is Milestone 11's concern (GCP deployment hardening),
  not built here.
- **A candidate matched to more than one signal has no dedicated UI distinguishing "why" each
  signal contributed** — they're just listed together; the relevance assessment reflects
  whichever signal triggered the triage call, not a synthesis across all linked signals (in
  practice, this milestone's `triage_signal` only ever links exactly one signal per candidate
  — a genuine multi-signal correlation step is future work).
- MCP gateway (Milestone 10) and GCP deployment hardening (11) are unchanged.
