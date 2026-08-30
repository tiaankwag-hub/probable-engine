# Milestone 1 Implementation Plan

**Not started.** This is the detailed plan requested for review before Milestone 1 begins.

## Scope

### Database (PostgreSQL + Alembic)
Tables: `users`, `roles`, `user_roles`, `risk_categories`, `risks`, `risk_assessments`,
`risk_impact_scores`, `risk_history`, `scoring_config` (minimal v1: a single active version,
full versioning UI deferred to Milestone 2/3), `risk_appetite` (schema only; evaluation logic
lands Milestone 3), `import_jobs`, `import_column_mappings`, `import_row_errors`,
`audit_events`.
Deliberately excluded from Milestone 1: controls, actions, issues, incidents, snapshots,
scenarios, simulations, emerging risk, AI, reports (their own milestones own the schema for
those tables, so Milestone 1's migration doesn't guess at requirements it will get more
precisely later).

### Backend (`apps/api`, `packages/shared`, `packages/risk_engine` stub)
- Risk Register CRUD: `GET/POST /api/v1/risks`, `GET/PATCH /api/v1/risks/{id}`,
  `GET /api/v1/risks/{id}/history`.
- Risk categories read endpoint.
- Import Wizard: all six endpoints in `docs/api/00-api-design.md`'s Import group, backed by
  the staging tables above. Commit path is asynchronous via the Milestone 1 slice of the
  job-queue abstraction (ADR 0005) even though the worker itself does little else yet.
- Audit event emission on every risk create/update and every import commit.
- RBAC dependency scaffolding covering the seven roles, applied to every route from day one
  (even if some roles have no Milestone-1-relevant permissions yet) so the pattern is set
  correctly before more routes are added.
- Mock-auth mode (seeded local users with role claims) per ADR 0010.
- `packages/risk_engine` gets only what's needed to compute `overall_impact` from the six
  impact dimensions using a hard-coded-in-config-but-not-in-code initial scoring config
  seeded via `database/seed` — inherent/residual/band logic (needing control effectiveness)
  is Milestone 2 scope; Milestone 1 stores raw impact/likelihood inputs correctly even before
  full scoring exists.

### Frontend (`apps/web`)
- Risk Register list (search, filter by category/status/owner, pagination).
- Risk detail/edit page (subset of fields relevant without controls/actions yet).
- Import Wizard: upload → column mapping → validation issues → preview → commit, matching
  the API step-for-step.
- Typed API client generated from the OpenAPI schema.

### Infrastructure
- `docker-compose.yml`: `postgres`, `api`, `web`. `worker` included as a container that runs
  the Milestone-1 job poller (import commit) even though it has no other job types yet.
- No GCP, no Terraform, no real secrets — `.env.example` only.

### Tests
- `packages/risk_engine`: unit tests for the Milestone-1 partial scoring function
  (`overall_impact` calculation), including edge cases (min/max scores, missing dimension).
- `apps/api`: integration tests for Risk CRUD (incl. optimistic-concurrency 409 case) and the
  full Import Wizard flow (happy path + a file with validation issues + a re-import matching
  an existing `risk_code` to confirm no silent overwrite).
- Role/access tests: every route exercised against all seven roles, asserting the RBAC matrix
  in `docs/api/00-api-design.md`.
- Frontend: component tests for the Import Wizard step flow; a Playwright smoke test for
  "create a risk, see it in the list" and "import a fixture file end-to-end".

## Acceptance criteria
- [ ] `alembic upgrade head` runs cleanly against a fresh local Postgres.
- [ ] All Milestone 1 pytest suites pass (`packages/risk_engine`, `apps/api` integration,
      role/access).
- [ ] Playwright smoke tests pass against the Compose stack.
- [ ] A fixture spreadsheet matching the brief's 37-column schema can be uploaded, mapped,
      validated, previewed, and committed through the UI, producing correct `risks` rows and
      an `audit_events` row.
- [ ] Re-importing the same fixture does not silently overwrite the committed rows — it
      surfaces a conflict requiring confirmation.
- [ ] RBAC is verified server-side (a Viewer token cannot create/edit a risk even if the
      request is crafted directly against the API, not just hidden in the UI).
- [ ] `docs/` updated to reflect anything that changed from this plan during implementation.

## Explicitly deferred out of Milestone 1
Inherent/residual scoring and bands (Milestone 2), controls/actions (Milestone 3), appetite
evaluation logic (Milestone 3), snapshots (Milestone 4), reporting (Milestone 5),
simulations (Milestone 6–7), AI (Milestone 8), emerging risk (Milestone 9), MCP (Milestone
10), real SSO/IAP and any GCP resource (Milestone 11).

## Open items to confirm with the user before/while implementing
- Confirm whether a real Risk Register spreadsheet will be provided to validate the Import
  Wizard against, or whether a synthetic fixture (matching the brief's documented schema) is
  acceptable for Milestone 1 sign-off.
- Confirm the enterprise component library choice for `apps/web` (ADR 0003 leaves this open).
