# Milestone 2 Implementation Plan — COMPLETE

Scope was narrowed from the roadmap's original "risk engine + dashboard + heatmap" framing
because the risk engine already shipped in Milestone 1 (see that plan's Deviations). This
milestone instead delivers the Executive Dashboard, the 5×5 heatmap, and the scoring-config
admin UI that consume it.

## What was built

### Backend
- `packages/shared/dashboard_service.py`: `compute_executive_dashboard()` — a pure
  aggregation function (given a DB session) producing total/band counts, overdue-review
  count, category exposure, risk-velocity mix, a 25-cell 5×5 heatmap (likelihood × impact,
  colored by dominant residual band), and a top-10 leadership-attention list ranked by
  residual score. Lives in `packages/shared` (not `apps/api`) so a future MCP `get_top_risks`
  tool or reporting job can reuse it rather than re-implementing the aggregation.
- `GET /api/v1/dashboard/executive` — read-only, any authenticated role (`VIEW_RISKS`).
- Scoring-config admin: `GET /api/v1/scoring-config` (version history, any role) and
  `POST /api/v1/scoring-config` (Administrator-only — new `MANAGE_SCORING_CONFIG`
  permission), which validates the payload through the same constraints
  `packages.risk_engine.ScoringConfigData` enforces (weights sum to 1.0, thresholds sorted),
  deactivates the previous version, and emits an audit event. Past `risk_assessments` rows
  keep their original `scoring_config_version`, so a config change never rewrites how a
  historical score is explained (ADR 0007).

### Observability (retroactive fix to a Milestone 1 gap)

The roadmap has claimed "structured logging with correlation/request/job/simulation/AI run
IDs" as present "from Milestone 1 onward" since Milestone 0 — Milestone 1 never actually
built it. Caught while reviewing the roadmap during this milestone rather than left
uncorrected: `packages/shared/logging.py` (a `contextvars`-based `request_id_var`/`job_id_var`
plus a JSON log formatter that includes whichever is set) and `apps/api/app/middleware.py`
(`RequestIdMiddleware` — generates or echoes `X-Request-Id`, logs one structured line per
request with method/path/status/latency). `apps/worker` sets `job_id_var` for the duration of
each job so its logs carry the job id the same way. Covered by
`apps/api/tests/test_observability.py`.

### Frontend
- `/dashboard` (now the post-login landing page): KPI tiles (total/extreme/high/moderate/
  low/overdue-reviews), the 5×5 heatmap, a residual-band-distribution bar chart, a
  category-exposure bar chart, a risk-velocity breakdown, and the top-risks table — all via
  Recharts (ADR 0003) on top of the same accessible severity color tokens used elsewhere
  (count is always shown as text, never color alone).
- `/admin/scoring-config`: version history table (visible to everyone) plus a "publish new
  version" form (Administrator-only, both hidden in the UI and enforced server-side).
- Navigation gains **Dashboard** for everyone and **Administration** for Administrators only.

### What was intentionally left out (and why)

The brief's Executive Dashboard section lists KPIs this milestone does not compute: Risks
Outside Appetite, Weak Controls, Overdue Actions, and Emerging Risks. Each depends on an
entity that doesn't exist yet — appetite evaluation, controls, and actions all land in
Milestone 3; emerging risks in Milestone 9. Faking those numbers against absent data would
violate the platform's own "no hard-coded business rules, nothing fabricated" quality bar,
so the dashboard shows exactly what it can honestly compute today and nothing more.

## Tests

- 5 `packages/shared` unit tests for `round_to_grid` (heatmap cell placement, including
  clamping and Python's banker's-rounding edge case at `x.5`).
- 8 `apps/api` integration tests for the dashboard endpoint: empty state, band counts,
  closed-risk exclusion, overdue-review detection, heatmap cell placement, top-risk ordering,
  category grouping, and auth enforcement.
- 7 `apps/api` integration/RBAC tests for scoring config: seeded version, non-administrator
  roles rejected (all 6 other roles individually), weight/threshold validation errors, and an
  end-to-end check that a new config changes how a *subsequent* reassessment scores without
  altering the risk's already-recorded history entry.
- 2 `apps/api` tests for the request-id middleware (generated when absent, echoed when the
  client supplies one).
- 2 new Playwright specs (`tests/e2e/specs/dashboard-and-admin.spec.ts`): the dashboard
  renders with real data for an Executive (and hides Administration from them), and an
  Administrator can publish a new scoring-config version through the UI.

**133 pytest tests + 4 Playwright specs, all passing** (up from 107 + 2 in Milestone 1).

## Bugs found and fixed during verification

- The scoring-config form's dimension-weight `<input type="number" step="0.01">` rejected
  its own default value (`0.1667`, from `1/6`) under native HTML5 step validation, silently
  blocking submission with no visible error until inspected in a real browser — exactly the
  kind of thing pytest can't catch. Fixed by using `step="any"`. Caught by the new Playwright
  spec, not by unit/integration tests, which only underlines why the brief requires
  browser-level verification for UI changes.
- Milestone 1's e2e spec asserted a fixed risk title, which would collide with itself on a
  second run against a persistent dev database (no fresh `docker compose down -v`). Made the
  title unique per run.

## Local demonstration

1. **Start:** `docker compose up --build` (from the repo root, after `cp .env.example .env`).
2. **Open:** http://localhost:3000
3. **What you should see and be able to test (in addition to everything from Milestone 1):**
   - Signing in now lands on the **Executive Dashboard** (`/dashboard`) instead of the Risk
     Register: KPI tiles reflecting the 20 seeded demo risks, a populated 5×5 heatmap, a
     residual-band bar chart, a category-exposure chart, a velocity breakdown, and a
     top-10 leadership list.
   - Sign in as `admin@example.com` and open **Administration** in the nav →
     `/admin/scoring-config`: see the seeded v1 configuration, and publish a new version —
     watch it appear in the version history as the new active version.
   - Sign in as any non-Administrator role and confirm the **Administration** link is absent
     and `/admin/scoring-config` shows a read-only history with no publish form (the API
     independently returns `403` if you try anyway — RBAC is enforced server-side).
   - Reassess a risk from its detail page (Milestone 1 feature) and confirm the dashboard's
     counts/heatmap update to match on next visit.
4. **Test credentials:** unchanged from Milestone 1 — see
   [`docs/architecture/milestone-1-plan.md`](milestone-1-plan.md#local-demonstration).
5. **Stop:** `docker compose down` (`-v` to also wipe the database/storage volumes).

Verified the same way as Milestone 1: this sandbox's network policy blocks Docker Hub pulls
(see Milestone 1's note), so the stack was run as local processes (`uvicorn`,
`python -m apps.worker.app.main`, `npm run dev`) against the same Postgres instance and env
vars the Compose file uses, with all 133 pytest tests and all 4 Playwright specs passing
against that live stack, plus a manual screenshot review of the dashboard.

## Explicitly still deferred

Appetite evaluation and controls/actions (Milestone 3), snapshots and trend history
(Milestone 4), reporting (Milestone 5), simulations (Milestone 6–7), AI (Milestone 8),
emerging risk (Milestone 9), MCP (Milestone 10), real SSO/IAP and GCP (Milestone 11).
