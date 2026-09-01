# Milestone 1 Implementation Plan — COMPLETE

Implemented, tested, and manually verified against a live stack (local Postgres, FastAPI,
worker, Next.js). All acceptance criteria met. See "Deviations from the original plan" below
for the two places implementation diverged from what was scoped, and why.

## What was built

### Database (PostgreSQL + Alembic)
One consolidated migration (`apps/api/alembic/versions/f150133b8154_*.py`) creates: `users`,
`roles`, `user_roles`, `risk_categories`, `risks`, `risk_assessments`, `risk_impact_scores`,
`risk_history`, `scoring_config`, `risk_appetite` (schema only — evaluation logic is still
Milestone 3), `import_jobs`, `import_column_mappings`, `import_row_errors`, `audit_events`,
and `background_jobs` (the local-dev side of the JobQueue abstraction, ADR 0005 — added during
implementation, see deviations). Verified with `alembic upgrade head` against both a dev and a
test database.

### Backend
- `packages/risk_engine`: full deterministic scoring pipeline — overall impact, inherent
  score/band, control-effectiveness reduction, residual score/band — config-driven per ADR
  0007, with 38 unit tests covering validation, banding boundaries, and determinism.
- `packages/shared`: SQLAlchemy models, Pydantic schemas, the audit-event writer, the RBAC
  permission matrix, the object-storage abstraction (local filesystem), the import-mapping
  layer (parser, transforms, default mapping template for the brief's 36-column schema,
  validation), and `risk_service`/`import_service` — the shared create/update/commit logic
  used identically by `apps/api` and `apps/worker`.
- `apps/api`: `/healthz`, `/readyz`, mock-auth login, Risk Register CRUD (list with
  search/filter/pagination, create, get, patch with optimistic concurrency, history,
  assessments), risk-categories read, and the full six-endpoint Import Wizard flow
  (upload → columns → mapping → validate → preview → commit). RBAC enforced server-side on
  every route via a FastAPI dependency.
- `apps/worker`: a `background_jobs` poller (`SELECT ... FOR UPDATE SKIP LOCKED`) that
  executes the import-commit job using the exact same `import_service.commit_import_job`
  the API would call inline — proving the async boundary works without inventing a second
  code path.

### Frontend (`apps/web`)
Next.js 16 (App Router) + TypeScript + Tailwind. Mock-auth sign-in, Risk Register list
(search, status filter, pagination, severity badges), risk create form, risk detail page
with in-place reassessment and version history, and the full Import Wizard UI
(upload → mapping → validation issues → preview → commit → live job-status polling).
`npm run build` and `tsc --noEmit` both pass; `npm audit` reports 0 vulnerabilities.

### Infrastructure
`docker-compose.yml` (postgres, api, worker, web) and a `Dockerfile` per service. Docker
Compose itself was **not** exercised end-to-end in this sandbox (no Docker daemon available
here — see deviations); the stack was instead validated by running each service as a local
process against the same Postgres instance and environment variables the Compose file uses,
which exercises the identical code paths.

### Seed data and synthetic fixture
`database/seed/seed.py` (roles, one user per role, starter categories, the active scoring
config) and `database/seed/generate_fixture.py`, which produced
`database/seed/fixtures/risk_register_fixture.xlsx` — 20 synthetic rows matching the brief's
36-column schema, all fabricated for this prototype.

### Tests
- 38 `packages/risk_engine` unit tests.
- 18 `packages/shared` import-mapping unit tests.
- 47 `apps/api` integration + RBAC tests (real Postgres, not SQLite — ADR 0004 stays true
  even in tests) covering risk CRUD, optimistic concurrency, the accept/rationale rule, the
  full import wizard flow, re-import non-overwrite, and the RBAC matrix across all 7 roles.
- 4 `apps/worker` tests covering the job poller (success, unknown job type, FIFO ordering).
- 2 Playwright end-to-end specs (`tests/e2e/specs/risk-register-and-import.spec.ts`) run
  against the live stack: "create a risk, see it in the list" and "import the fixture
  end-to-end", both passing.

**107 pytest tests + 2 Playwright specs, all passing.**

## Local demonstration

1. **Start:** `docker compose up --build` (from the repo root, after `cp .env.example .env`).
   This builds all four services, runs migrations, and seeds the database automatically —
   nothing else to run.
2. **Open:** http://localhost:3000
3. **What you should see and be able to test:**
   - Sign-in screen listing 7 seeded users (one per role).
   - **Risk Register** (`/risks`): 20 pre-seeded synthetic risks, searchable by title/code,
     filterable by status, with color-coded inherent/residual severity badges; "New risk"
     opens a full create form with the six impact dimensions and likelihood.
   - **Risk detail** (click any risk): full field view, "Record new assessment" to re-score a
     risk in place (bumps version, appends history), and a version history list.
   - **Import Wizard** (`/imports`): upload `database/seed/fixtures/risk_register_fixture.xlsx`
     (or any `.xlsx` with a similar layout) → review/adjust the suggested column mapping →
     validate (blocking vs. warning issues shown separately) → preview mapped rows → commit
     → watch the job status poll from "pending" to "succeeded". Re-uploading the same file
     shows every row skipped as an existing-risk conflict — nothing is silently overwritten.
   - Try signing in as `viewer@example.com` and confirm "New risk" is not permitted (RBAC is
     enforced server-side, not just hidden in the UI).
4. **Test credentials** (local mock authentication only — ADR 0010, not a real login):
   | Email | Role |
   |---|---|
   | `viewer@example.com` | Viewer |
   | `risk.owner@example.com` | Risk Owner |
   | `control.owner@example.com` | Control Owner |
   | `risk.manager@example.com` | Risk Manager |
   | `executive@example.com` | Executive |
   | `admin@example.com` | Administrator |
   | `auditor@example.com` | Auditor |

   No password — pick the email from the dropdown on the sign-in screen.
5. **Stop:** `docker compose down` (add `-v` to also delete the Postgres/storage volumes and
   start fresh next time).

**A note on how this was verified.** This session runs inside a sandboxed development
environment whose network egress policy blocks pulls from Docker Hub's CDN
(`production.cloudfront.docker.com` returns a policy `403`) — `docker compose up --build`
itself could not be executed to completion here, and `docker compose config` was used
instead to confirm the file parses and wires services/health-conditions correctly. The
application logic behind it was fully verified by running each service as a local process
(`uvicorn`, `python -m apps.worker.app.main`, `npm run dev`) against the same PostgreSQL
instance and environment variables the Compose file uses, including the 107 automated tests
and the 2 Playwright end-to-end specs against that live stack. This restriction is specific
to this sandbox — a normal Docker Desktop installation (like the Mac this platform targets)
has unrestricted access to Docker Hub, so `docker compose up --build` is expected to work
as documented. **Recommended:** run it once yourself early and report back if anything
differs from what's described above, so it can be fixed immediately rather than discovered
at a later milestone.

## Acceptance criteria

- [x] `alembic upgrade head` runs cleanly against a fresh local Postgres.
- [x] All Milestone 1 pytest suites pass (`packages/risk_engine`, `packages/shared`,
      `apps/api`, `apps/worker`).
- [x] Playwright smoke tests pass against the running stack.
- [x] The synthetic fixture spreadsheet can be uploaded, mapped, validated, previewed, and
      committed through the UI, producing correct `risks` rows and an `audit_events` row.
- [x] Re-importing the same fixture does not silently overwrite the committed rows — it is
      skipped per row and recorded as an `existing_risk_conflict` issue.
- [x] RBAC is verified server-side (a Viewer token gets `403` creating a risk directly
      against the API, not just hidden in the UI).
- [x] `docs/` updated to reflect what changed from the original plan (this document).
- [x] Database seeds automatically (roles, users, categories, scoring config, and 20 demo
      risks) on startup so the UI is populated immediately — no manual seed step required.

## Deviations from the original plan

1. **Full scoring, not a partial stub.** The original plan scoped Milestone 1 to only
   `overall_impact` and pushed inherent/residual scoring and bands to Milestone 2. During
   implementation this split proved artificial: `packages/risk_engine` is a small, pure,
   fully-testable package regardless of how much of the pipeline it covers, and a Risk
   Register that can't show a residual band isn't a usable slice to demo. The complete
   pipeline (ADR 0007) was built and tested in Milestone 1 instead. **Effect on the
   roadmap:** Milestone 2 no longer needs to build core scoring — it now focuses on the
   scoring-config admin UI, the executive dashboard, and the 5×5 heatmap, which consume the
   scoring already in place.
2. **Component styling, not full shadcn/ui.** ADR 0003 selected shadcn/ui (Radix primitives
   + Tailwind). Milestone 1's UI needs (buttons, selects, a badge, tables, forms) were built
   as plain accessible HTML elements styled with Tailwind rather than pulling in
   `@radix-ui/*` and running the shadcn CLI, to keep the dependency surface minimal for a
   CRUD-and-wizard slice. This is a gap against the ADR, not a reversal of it: Milestone 2's
   heatmap and any dropdown/dialog-heavy Simulation Lab UI genuinely need Radix's focus
   management, and that's when the shadcn primitives should actually be introduced.
3. **Docker Compose written and structurally validated, but not run to completion here.**
   The Docker daemon does run in this sandbox, but its network egress policy blocks pulls
   from Docker Hub's CDN — see "A note on how this was verified" under **Local
   demonstration** above for the exact failure and why it's a sandbox-specific restriction
   rather than an application defect. `docker compose config` confirms the file is
   syntactically valid and the service graph (including the `migrate` → `api`/`worker`
   `service_completed_successfully` dependency) resolves correctly; the underlying logic was
   verified end-to-end via the equivalent local-process route. `docker compose up --build`
   itself should still be the first thing run in an environment with unrestricted Docker Hub
   access, precisely because it's the one thing that couldn't be exercised directly here.
4. **Next.js 16, not an unpinned "latest".** `npm install` initially resolved Next.js 14.2.18
   with one critical and four high-severity advisories (see `npm audit`). Next 14's patched
   line (14.2.35) still carried several of the same high-severity advisories unresolved
   until Next 16. Next 16.3.3 still supports React 18 (no forced React 19 upgrade) and this
   app uses only client components, so the App Router server-component breaking changes in
   Next 15/16 don't apply here. Upgraded to Next 16.3.3 + eslint 9 (a peer requirement of
   `eslint-config-next@16`); `npm audit` now reports 0 vulnerabilities.

## Explicitly still deferred (unchanged from the original plan)

Appetite evaluation logic and controls/actions (Milestone 3), snapshots (Milestone 4),
reporting (Milestone 5), simulations (Milestone 6–7), AI (Milestone 8), emerging risk
(Milestone 9), MCP (Milestone 10), real SSO/IAP and any GCP resource (Milestone 11).

## Resolved open items

Both items the Milestone 0 report flagged for the user were resolved before implementation
began: use a synthetic fixture matching the documented schema (confirmed), and shadcn/ui was
selected for the component library (ADR 0003) — see deviation #2 above for how far that
landed in Milestone 1 itself.

## Post-Milestone-9 enhancement: downloadable Risk Register import template

Requested directly by the user, ahead of Milestone 10: a downloadable `.xlsx` template on the
Import Wizard's upload step so they know exactly what to fill in from their real risk register
without trial-and-error against validation errors.

`templates/import/build_risk_register_template.py` generates it by reading the column list,
required/optional split, enum values, and scoring formulas directly from
`packages/shared/importing/mapping.py`, `validation.py`, `transforms.py`, and
`packages/risk_engine/scoring.py` — not from the brief's original documented 34-column
assumption used to build `DEFAULT_RISK_REGISTER_MAPPING`. It deliberately narrows that set to
24 columns: excludes the 6 platform-calculated reference columns (`*_calc` — the user
explicitly asked these not be visible/fillable, and the platform always recomputes them
itself) and 6 more columns the mapper accepts but `row_to_inputs()`/`create_risk()` never
actually reads today (`key_controls_ids_or_short_list`, `actions_link_jira_servicenow_etc`,
`due_date`, `completion`, `updated_by`, `last_updated_date`) — filling those in would silently
do nothing, so leaving them in the template would be a trap, not a convenience. Headers are
the exact `source_column` strings `DEFAULT_RISK_REGISTER_MAPPING` already auto-maps, so
uploading a correctly-filled template needs zero manual remapping in the wizard's step 2.

The generated workbook: a "Risk Register" data tab (color-coded required/conditional/optional
headers, a per-column cell comment repeating the rule, data-validation dropdowns for
`status`/`decision`, a whole-number 1-5 validation on every impact/likelihood/control-
effectiveness column, a custom `COUNTIF` validation blocking a duplicate `risk_id` within the
sheet, and one realistic worked example row) plus an "Instructions & Scoring" tab spelling out
how Overall Impact, Inherent Score/Band, the control-effectiveness reduction, and Residual
Score/Band are actually computed (values pulled from `default_scoring_config()`, with an
explicit note that an Administrator can change them later via the Scoring Config admin page).
The data tab is deliberately first in the workbook — `parser.py` only ever reads
`wb.worksheets[0]`, so the Instructions tab has to come second regardless of what a user might
rename tabs to.

Verified against the real pipeline, not just visually: `parse_columns`/`parse_rows` on the
generated file map every header with zero manual remapping, and `validate_rows` on its own
example row returns zero issues (not even warnings). Re-verified live in the browser — the
exact file served from `apps/web/public/templates/risk-register-import-template.xlsx` was
downloaded, uploaded through the actual Import Wizard UI, validated with "0 issue(s) found",
and committed successfully, producing a real risk whose computed inherent/residual bands
matched the Instructions tab's formulas exactly.

## Post-Milestone-9 enhancement: executive-summary depth, risk-tolerance sliders, Guided Risk Intake

Three requests in one sitting, all shipped incrementally on top of the existing AI/appetite
architecture without a schema change to `risks` or a new suggestion-review mechanism except
where noted.

**Executive Summary** (`packages/shared/ai_service.py`'s `build_executive_summary_context`)
went from four KPI counts to a full board briefing: category exposure, governance/control
health, the risk-appetite/tolerance position (`compute_governance_health`'s
`appetite_status_counts`), a deterministic trend judgment computed in Python from
`compute_trend`'s last two points (never left to the model to eyeball), and unresolved
Emerging Risk Radar signals as the horizon-watch source. The prompt (`EXECUTIVE_SUMMARY_PROMPT`
in `packages/ai/gemini_provider.py`) asks for three grounded paragraphs — posture, focus and
trajectory tied explicitly to appetite, and horizon watch inside and outside the organization —
and requires the model to say when it's applying general judgment rather than register data.
The mock provider mirrors the same structure deterministically. No new capability, migration,
or job type: this was a context-and-prompt change only.

**Risk-tolerance sliders**: the Admin → Risk Appetite page replaced its `appetite_band`/
`tolerance_band` `<select>`s with a 4-stop ordinal slider each (dragging appetite past the
current tolerance brings tolerance up with it, mirroring `AppetiteThresholds`'s own
`tolerance_band must be at or above appetite_band` rule) and replaced the bare numeric
`limit_value` input with a continuous slider rendered against the active scoring config's own
band boundaries, so the material-breach ceiling is set in visual context rather than guessed
as a number. Purely a frontend change — `risk_appetite`'s schema and `evaluate_appetite()`
were untouched.

**Guided Risk Intake** (`packages/shared/models/risk_intake.py`,
`packages/shared/risk_intake_service.py`, `apps/api/app/routers/risk_intake.py`,
`apps/web/app/risk-intake/page.tsx`): a live, turn-by-turn chat for a non-expert user or an
ELT member who wants to raise a concern but doesn't know the register's terminology. This is
the one genuinely new architectural shape in the AI layer — every other capability dispatches
through a `BackgroundJob` (ADR 0005) and is polled; a conversation needs to feel like a
conversation, so each turn is a direct, synchronous call to the active `AIProvider` from
`apps/api` itself. A new `continue_risk_intake` capability (`IntakeTurnResult`, its own shape
like `CandidateAssessment` — not an `AIResponse`, since a turn is one reply plus an incremental
structured extraction, not a narrative-plus-suggestions) walks toward a fixed backbone of six
fields (what could happen, impact, cause, department, a category guess, a title); the mock
provider walks the same six questions in a deterministic script, the Gemini provider phrases
them adaptively and can ask a clarifying follow-up. `MAX_INTAKE_TURNS = 6` is a hard guardrail
enforced in `submit_user_message()` itself, never left to the provider's judgment, so a session
can never trap a user in an endless back-and-forth.

Finishing a session does **not** go through the `AISuggestion` review queue — it creates a
`draft`-status `Risk` directly, through the exact same `create_risk()` every other
risk-creation route uses, with the same minimal unrated placeholder assessment
(likelihood=1, every impact dimension=1, no control effectiveness) as an approved
emerging-risk suggestion. That's a deliberate call: unlike the Emerging Risk Scan (an AI
autonomously mining the whole register for a gap nobody asked about), this is a human directly
authoring their own submission with AI only helping structure the wording — much closer to the
Import Wizard's direct-commit-to-draft than to an AI proposal awaiting approval. The submitting
user becomes the risk's owner; `latest_update` carries a provenance breadcrumb naming the
intake session so a reviewer knows why an otherwise-normal draft has no real assessment yet.

RBAC added `SUBMIT_RISK_INTAKE` (risk_owner, control_owner, risk_manager, **executive**,
administrator — deliberately broader than `CREATE_OWN_RISK`, since the point was reaching ELT
members and other roles that can't otherwise create a risk manually) and `REVIEW_RISK_INTAKE`
(risk_manager/administrator, mirroring `REVIEW_EMERGING_RISKS`'s boundary exactly) for a
review-inbox view of every submitted session across users, without granting the ability to
chat or submit as someone else. `viewer` and `auditor` — the platform's two read-only/
compliance roles — get neither.

Verified live end-to-end with both providers: a full six-turn conversation through the mock
provider produces a `ready_to_submit` session whose "Submit for review" button creates a real
draft `Risk` visible in the register and in the Risk Manager's review inbox; the seed script's
new `seed_demo_risk_intake_content` walks the same conversation through the same service
functions (not hand-built rows) so the feature has real demo data on a fresh environment.
