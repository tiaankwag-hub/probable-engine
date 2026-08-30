# Milestone 3 Implementation Plan — COMPLETE

Controls, Actions, Risk Appetite, and Governance Health — all first-class entities per the
brief, with real RBAC-scoped ownership rules mirroring the pattern Milestone 1 established
for risks.

## What was built

### Database (PostgreSQL + Alembic)
New migration adds `controls`, `risk_controls` (many-to-many), `control_tests`, and
`actions`. `risk_appetite` (schema-only since Milestone 1) now has real evaluation logic
behind it.

### Backend
- **`packages/risk_engine/appetite.py`**: pure, deterministic appetite evaluation
  (`within_appetite` / `approaching_tolerance` / `outside_appetite` / `material_breach` /
  `not_configured`) — same pattern as scoring (ADR 0007 extended to appetite): nothing
  hard-coded, a database row in, a status out, 12 unit tests.
- **`packages/shared/appetite_repo.py`**: resolves which `risk_appetite` row applies to a
  risk (most-specific category+business-unit match wins, respecting effective dates).
- **`packages/shared/governance_service.py`**: bulk aggregation for weak controls (latest
  effectiveness ≤ 2/5), overdue actions, overdue reviews, and appetite-status counts —
  fetches all appetite rows once rather than per-risk, so it doesn't degrade as the register
  grows.
- **Controls API**: full CRUD, ownership-scoped like risks (`Control Owner` manages their
  own; `Risk Manager`/`Administrator` manage any). Recording a control test
  (`POST /controls/{id}/tests`) is the *only* way a control's `operating_effectiveness`
  changes — derived from the most recent test's result, never edited directly.
- **Actions API**: full CRUD with an `?overdue=true` filter, ownership-scoped the same way.
  Marking an action `completed` auto-sets `completion_percent=100` and `completed_date`.
- **Risk↔Control linking**: `GET/POST /risks/{id}/controls`,
  `DELETE /risks/{id}/controls/{control_id}` — gated by the same "can you edit this risk"
  rule as everything else on a risk, not a separate permission.
- **Risk Appetite config**: `GET/POST/PATCH /risk-appetite`, Administrator-only writes
  (`MANAGE_APPETITE`), validated (bands must be real values, tolerance ≥ appetite,
  `effective_to` ≥ `effective_from`).
- **Governance Health**: `GET /dashboard/governance` — weak controls, overdue actions,
  overdue reviews, appetite-status counts, and the list of risks outside appetite.
- **Executive Dashboard enriched**: the three KPIs Milestone 2 explicitly deferred rather
  than fake (Risks Outside Appetite, Weak Controls, Overdue Actions) are now real, backed by
  the same `governance_service` functions.
- `RiskDetailOut` (single-risk reads only) now includes `appetite_status`.

### Frontend
`/controls` (list + create), `/controls/[id]` (detail + record-test form), `/actions`
(list, overdue/status filters, inline "mark complete"), `/governance` (Governance Health
page), `/admin/appetite` (Administrator-only threshold configuration). Risk detail page
gained a Controls panel (link/unlink) and an Actions panel (list + quick-create), plus an
Appetite status line next to Inherent/Residual. Executive Dashboard gained a second KPI row
for the three newly-available metrics.

### Seed data
`database/seed/seed.py` now derives 6 controls and ~20 actions from the same fixture
spreadsheet rows that produce the demo risks — reusing the `control_ids_raw` and
`treatment_summary`/`action_completion_raw`/`action_due_date_raw` fields the Import Wizard
already parses but Milestone 1 didn't yet have a table for. Effectiveness values were chosen
to match the fixture's own narrative (e.g. the unpatched-servers risk cites weak
scanning/patching controls, seeded at 2/5) rather than being arbitrary. All fixture due dates
predate the current date, so overdue actions are visible immediately without extra seeding
logic.

## Tests

- 12 `packages/risk_engine` appetite unit tests.
- 41 new `apps/api` integration/RBAC tests: Controls (ownership rules, test recording
  updating effectiveness, risk-control linking), Actions (creation, ownership-scoped
  editing, overdue filtering, completion), Risk Appetite (Administrator-only, validation),
  Governance Health (weak controls, overdue actions/reviews, appetite breach detection, the
  enriched Executive Dashboard).
- 2 new Playwright specs (`tests/e2e/specs/governance-controls-actions.spec.ts`): Controls/
  Actions/Governance pages render seeded data; a Risk Owner can link a control and create an
  action from the risk detail page end-to-end.

**186 pytest tests + 6 Playwright specs, all passing** (up from 145 + 4 after Milestone 2).

## Local demonstration

1. **Start:** `docker compose up --build` (from the repo root, after `cp .env.example .env`).
2. **Open:** http://localhost:3000
3. **What you should see and be able to test (in addition to Milestones 1–2):**
   - **Executive Dashboard** now shows Risks Outside Appetite, Weak Controls, and Overdue
     Actions alongside the Milestone 2 KPIs.
   - **Controls** (`/controls`): 6 seeded controls with varying effectiveness (color-coded —
     red at ≤2/5); open one to record a new test and watch its operating effectiveness
     update immediately.
   - **Actions** (`/actions`): ~20 seeded actions, mostly overdue (the fixture's due dates
     predate today); filter by overdue/status, mark one complete.
   - **Governance Health** (`/governance`): weak controls, overdue actions/reviews, and
     appetite-status breakdown in one place — this is the page a Risk Manager would actually
     watch day to day.
   - **Risk detail**: open any risk to see its linked controls (link/unlink another one),
     its actions (create a new one inline), and its live appetite status.
   - Sign in as `admin@example.com`, open **Risk Appetite** in the nav, and add a threshold
     for a category — then revisit that category's risks to see their appetite status
     change from "not configured" to a real evaluation.
   - Confirm RBAC: sign in as `control.owner@example.com` and try editing a control you
     don't own (403), or as `viewer@example.com` and confirm Controls/Actions creation is
     unavailable.
4. **Test credentials:** unchanged — see
   [`docs/architecture/milestone-1-plan.md`](milestone-1-plan.md#local-demonstration).
5. **Stop:** `docker compose down` (`-v` to also wipe volumes).

Verified the same way as prior milestones (this sandbox's Docker Hub pull restriction is
unchanged — see Milestone 1's note): every service run as a local process against the same
Postgres instance and environment variables the Compose file uses, with all 186 pytest tests
and all 6 Playwright specs passing, plus manual screenshot review of every new page.

## Bugs found and fixed during verification

- Built the three new Executive Dashboard KPIs (Risks Outside Appetite, Weak Controls,
  Overdue Actions) into the backend aggregation and TypeScript types, but initially forgot
  to add the corresponding `<KpiTile>` elements to the dashboard page itself — the API
  returned correct data the UI silently didn't render. Caught by screenshot review, not by
  any automated test (the existing dashboard tests only assert against the API response, not
  what's on screen) — now fixed and would be worth a Playwright assertion in a future pass.

## Explicitly still deferred

Issues and Incidents were in the original brief but never assigned a milestone in the
roadmap — a gap in Milestone 0's planning, not a deliberate cut. Rather than scope-creep
Milestone 3 (already Controls + Actions + Appetite + Governance Health) or leave them
homeless indefinitely, they're now explicitly assigned to Milestone 4, where they pair
naturally with "What Changed?" (an incident is exactly the kind of event a change narrative
should surface). Snapshots/trends (Milestone 4), reporting (5), simulations (6–7), AI (8),
emerging risk (9), MCP (10), real SSO/IAP and GCP (11) are unchanged.
