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
3. **Docker Compose written but not executed.** This sandbox has no running Docker daemon.
   The Compose file and Dockerfiles were authored to the same environment variables and
   commands used to run each service directly (which *was* verified end-to-end, including
   the Playwright specs), so the risk is limited to Docker-specific issues (build context,
   image layering) rather than application logic. Running `docker compose up` should be the
   first thing verified in an environment with Docker available before trusting this further.
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
