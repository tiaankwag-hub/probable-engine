# Milestone 4 Implementation Plan — COMPLETE

Snapshots, "What Changed?", trend charts, and Issues/Incidents — the last of the four
milestones absorbed from Milestone 0's original gap (Issues/Incidents were in the brief but
never assigned a milestone; see Milestone 3's "Explicitly still deferred" note).

## What was built

### Database (PostgreSQL + Alembic)
New migration adds `snapshots`, `snapshot_risks`, `issues`, and `incidents`. A snapshot
freezes each risk's leadership-relevant fields (status, band, score, owner, appetite status)
at a point in time via `SnapshotRisk.frozen_state` (JSONB) — deliberately not a replay of
`risk_history`, so "What Changed?" stays a simple diff against a named prior period rather
than an event-sourcing reconstruction. Actions/controls are not snapshotted in this
milestone — "changed" is scoped to risk-level fields; extending it is future work, not a
silent gap.

### Backend
- **`packages/shared/snapshot_service.py`**: `capture_snapshot()` freezes every risk
  (including closed ones, so a later comparison can see the closure) and audit-logs the
  capture; `compute_what_changed(since_snapshot_id)` diffs live risks against a snapshot's
  frozen state to detect new/closed/escalated/downgraded/owner-changed/appetite-changed
  risks, raising `ValueError` (→ 404) for an unknown snapshot; `compute_trend()` returns one
  point per snapshot plus a final "Current" point from live data, excluding closed risks from
  band counts.
- **Issues and Incidents**: deliberately thin, human-authored records — an incident is
  evidence a human reviews, not a silent risk mutation. `Incident.suggests_likelihood_increase`
  is just a flag a human sets; the only thing that actually changes a risk is the explicit
  `POST /incidents/{id}/trigger-review` action, which sets `risk.next_review_date` to today
  and stamps `incident.review_triggered_at` (never both automatically from the same write).
- **Snapshots API**: `GET/POST /api/v1/snapshots` (create requires `MANAGE_SNAPSHOTS` — Risk
  Manager/Administrator only; list is open to any authenticated viewer).
- **Dashboard additions**: `GET /api/v1/dashboard/what-changed?since_snapshot=<uuid>`,
  `GET /api/v1/dashboard/trends`.
- **Issues/Incidents API**: `GET/POST /api/v1/issues`, `PATCH /api/v1/issues/{id}` (status
  only); `GET/POST /api/v1/incidents`, `POST /api/v1/incidents/{id}/trigger-review` (400 if
  the incident has no linked risk, 403 unless the caller has `TRIGGER_INCIDENT_REVIEW` — Risk
  Manager/Administrator). Both auto-generate codes (`ISS-####`/`INC-####`) and support
  `GET /api/v1/risks/{id}/issues` / `.../incidents` for the risk-scoped view.
- **RBAC**: new permissions `MANAGE_SNAPSHOTS`, `CREATE_ISSUE`, `CREATE_INCIDENT`,
  `TRIGGER_INCIDENT_REVIEW` — issue/incident creation open to Risk Owner, Control Owner, Risk
  Manager, Administrator; snapshot management and review-triggering restricted to Risk
  Manager and Administrator.

### Frontend
- **`/snapshots`**: lists captured snapshots with risk counts; a capture form (Risk
  Manager/Administrator only, gated client-side on `session.roles` matching the API's own
  enforcement); a snapshot selector drives a "What Changed?" view with six panels (new,
  closed, escalated, downgraded, owner changes, appetite changes), each linking back to the
  affected risk.
- **`/trends`**: KPI tiles for the current band distribution plus a Recharts line chart
  (one line per band, plus total) across all captured snapshots and the current state; falls
  back to a plain message when fewer than two points exist rather than rendering a
  meaningless single-point chart.
- **Risk detail page**: two new panels, Issues (list + inline create) and Incidents (list +
  inline create with a severity selector), each showing the record's status/review state.
  Incidents show a "Trigger review" action, visible only to Risk Manager/Administrator, that
  disappears once `review_triggered_at` is set.
- **Nav**: added Snapshots and Trends links.

### Seed data
`database/seed/seed.py` gained two new idempotent functions, following the same
per-entity-idempotency lesson learned from the Milestone 3 seed bug (see that plan's "Bugs
found and fixed" section) rather than an all-or-nothing early return:
- `seed_demo_snapshot()`: seeds one fabricated snapshot dated ~30 days ago, built from each
  risk's *current* state with a handful of fields deliberately altered for specific,
  documented `risk_code`s (one risk excluded entirely to simulate "raised since baseline",
  one shifted a band down to show as escalated now, one shifted a band up to show as
  downgraded now, one flipped from closed to open to show as closed now, one owner
  reassigned) — this is fabrication in the same spirit as the fixture spreadsheet itself
  (see `docs/architecture/00-current-state-assessment.md`), never presented as real history,
  confined to the seed layer, and clearly commented in the source.
- `seed_demo_issues_and_incidents()`: seeds one issue and one incident tied to the fixture's
  own unpatched-servers risk/scanning-control narrative, so the new panels have real content
  immediately instead of being empty until a user creates one.

Both functions check their own table's existence independently of whether risks already
exist, so re-running the seed script against an already-seeded database (the exact scenario
that caused the Milestone 3 bug) correctly backfills these new entities without needing
`docker compose down -v`.

## Tests

- 8 `apps/api` unit tests for `snapshot_service` (capture, new/closed/escalated/downgraded/
  owner-change detection, unknown-snapshot `ValueError`, trend points including the "Current"
  point, closed-risk exclusion from trend counts).
- 8 `apps/api` integration tests for the Snapshots/What-Changed/Trends API (capture
  permission across all 6 non-manager roles, list, what-changed new-risk detection, 404 on
  unknown snapshot, 401 unauthenticated, trend current-point presence, trend reflecting a
  captured snapshot's label).
- 10 `apps/api` integration tests for Issues/Incidents (creation permission, viewer 403,
  status update, risk-scoped list for both; incident trigger-review success path, 403 for a
  non-manager, 400 with no linked risk).
- 3 regression tests (`test_seed_script.py`, added during Milestone 3's bug fix, still
  exercised here) confirming the seed script backfills correctly on re-run.

**215 pytest tests, all passing** (up from 189 mid-Milestone-4 backend work, now including
the snapshot/issues/incidents suites above). Frontend verified via `npx tsc --noEmit` and
`npm run build` (both clean, `/snapshots` and `/trends` present in the route manifest) plus
manual Playwright-driven screenshot review of all three new/changed pages against a live
local stack: Snapshots (capture + What-Changed panels showing the seeded escalate/downgrade/
new/closed/owner-change data correctly), Trends (line chart rendering), and Risk detail
(Issues/Incidents panels showing seeded `ISS-0001`/`INC-0001`, and the "Trigger review"
button verified end-to-end — clicking it set the risk's `next_review_date` via the API and
the button correctly disappeared afterward).

## Local demonstration

1. **Start:** `docker compose up --build` (from the repo root, after `cp .env.example .env`).
2. **Open:** http://localhost:3000
3. **What you should see and be able to test (in addition to Milestones 1–3):**
   - **Snapshots** (`/snapshots`): one seeded snapshot ("30 days ago") with a risk count;
     the What-Changed comparison against it shows two new risks, one closed risk, one
     escalated risk (with the band change badge), one downgraded risk, and one owner change
     — all seeded so this is populated immediately, not empty. Sign in as
     `risk.manager@example.com` or `admin@example.com` to also see the capture-snapshot form
     and try capturing a new one yourself.
   - **Trends** (`/trends`): a line chart of residual band counts across the seeded snapshot
     and the current live state — capture another snapshot from the Snapshots page and
     revisit this page to see the trend line grow a third point.
   - **Risk detail**: open `RSK-1002` ("Unpatched internet-facing servers") to see its seeded
     Issue (`ISS-0001`) and Incident (`INC-0001`); as `risk.manager@example.com` or
     `admin@example.com`, click "Trigger review" on the incident to set the risk's next
     review date and watch the button disappear. Any signed-in user (Risk Owner, Control
     Owner, Risk Manager, Administrator) can log a new issue or incident inline on any risk's
     detail page.
   - Confirm RBAC: sign in as `viewer@example.com` and confirm the capture-snapshot form and
     "Trigger review" action are both absent, and that issue/incident creation is refused by
     the API (403) if attempted directly.
4. **Test credentials:** unchanged — see
   [`docs/architecture/milestone-1-plan.md`](milestone-1-plan.md#local-demonstration).
5. **Stop:** `docker compose down` (`-v` to also wipe volumes).

Verified the same way as prior milestones (this sandbox's Docker Hub pull restriction is
unchanged — see Milestone 1's note): every service run as a local process against the same
Postgres instance and environment variables the Compose file uses, migrations applied with
Alembic, the seed script re-run against a database that already had Milestone 1–3 data to
confirm in-place backfill, all 215 pytest tests passing, and manual Playwright screenshot
review of every new/changed page including the trigger-review action's actual effect on the
underlying risk record.

## Bugs found and fixed during verification

None new. The seed script's idempotency discipline established while fixing Milestone 3's
bug (check each entity's own existence, never an all-or-nothing early return) was applied
from the start to `seed_demo_snapshot()` and `seed_demo_issues_and_incidents()`, and verified
directly: ran the seed script twice in a row against the dev database and confirmed row
counts for snapshots/snapshot_risks/issues/incidents were identical after the second run.

## Explicitly still deferred

- Actions and Controls are not captured in snapshots, so "What Changed?" cannot yet report a
  new control or a completed action — only risk-level fields.
- No scheduled/automatic snapshot capture (e.g. end-of-month cron); capture is manual via the
  UI or API, which is consistent with this milestone's scope (the automation would belong
  with a scheduler, out of scope until Milestone 11's GCP infrastructure work, or an interim
  worker job if requested).
- PowerPoint/PDF reporting (Milestone 5), Monte Carlo simulations (6–7), AI integration (8),
  Emerging Risk Radar (9), MCP gateway (10), and GCP hardening (11) are unchanged.
