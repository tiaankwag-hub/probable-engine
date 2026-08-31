# Milestone 6-7 Implementation Plan — COMPLETE

Risk-level Monte Carlo (Milestone 6) and scenario analysis with portfolio Monte Carlo
(Milestone 7), delivered together at the user's request. Documented as one plan since the
two milestones share a single engine and a single set of tables — Milestone 7's portfolio
run is not a separate system, it's Milestone 6's per-risk engine invoked once per linked
risk and correlated together.

## What was built

### `packages/simulations` (new package) — pure engine, no database dependency
- **`distributions.py`**: severity samplers for Triangular (`random.triangular`), PERT
  (Beta-PERT via `random.betavariate`, reshaped so its mean matches the classic
  `(min + 4×most_likely + max) / 6` weighting), and Lognormal (calibrated so
  `most_likely` is the median and `max` lands at the 95th percentile — a lognormal has no
  hard upper bound, so this is a documented, deliberate approximation, not a general-purpose
  fit). Also a Poisson sampler (Knuth's algorithm) for event counts. Deliberately stdlib-only
  — `random` and `statistics.NormalDist` cover everything needed without pulling in
  numpy/scipy for a prototype-scale engine.
- **`engine.py`**: the actual Monte Carlo — each iteration is one simulated year: event count
  ~ Poisson(`annual_event_frequency`), each event's severity drawn from the configured
  distribution, annual loss = sum of that year's severities (0 if no events). This is the
  standard actuarial frequency-severity shape, not a single per-iteration draw — it's what
  makes `annual_event_frequency` actually mean something. Produces expected annual loss,
  median, P75/P90/P95/P99, and a histogram for charting.
- **Portfolio correlation (`correlate_series`, `generate_reference_normals`,
  `run_portfolio_simulation`)**: risks that share a `correlation_group` are correlated via
  Iman-Conover rank-matching against a shared systemic normal factor — each risk still runs
  its own independent frequency-severity model untouched, then its resulting loss series is
  *reordered* (never transformed) so its rank order matches a reference series blending a
  common factor and its own idiosyncratic factor. This preserves each risk's exact marginal
  distribution while inducing realistic co-movement, and works identically regardless of
  which of the three distributions a risk uses — no inverse-CDF machinery needed for PERT's
  Beta distribution, which has no closed form. A dedicated test proves the correlated pair's
  measured Pearson correlation is higher than an otherwise-identical independent pair (see
  Tests below) — the correlation isn't just plumbed through, it's confirmed to work.
- **Tail-risk contribution**: for a portfolio run, each linked risk's average loss across the
  iterations where portfolio-wide loss lands in the worst 5% (P95+), normalized so all risks'
  shares sum to 1 — the metric a board pack actually wants ("who's driving the bad years"),
  not just each risk's standalone loss stats.
- Everything is reproducible: every run stores its `seed`, and a portfolio run derives each
  risk's own seed and each correlation group's common-factor seed deterministically from the
  run's single seed plus each risk's position in the list — never from Python's
  process-randomized `hash()`, which would break reproducibility across runs/processes.

### Database (PostgreSQL + Alembic)
New migration adds `simulation_configs` (one risk's frequency-severity parameters — always
belongs to exactly one risk), `simulation_runs` (executes either one config *or* one
scenario — exactly one of `config_id`/`scenario_id` is set, validated in the service layer
matching this codebase's existing pattern for optional either/or FKs), `simulation_results`
(percentiles, histogram, and — portfolio runs only — per-risk tail contribution, all in one
row), `scenarios`, and `scenario_risks`. The domain model's separate `reports`-style
definition table for simulation configs was never called for here since a config already
*is* the definition (see `docs/architecture/02-domain-model.md`'s `simulation_configs` entry)
— no further simplification was needed, unlike Milestone 5's `reports`/`report_runs` split.

### Backend
- **`packages/shared/simulation_service.py`**: the only place that bridges the pure engine
  and the database — converts a `SimulationConfig` row into the engine's `SimulationParams`,
  runs a single-risk simulation, and runs a portfolio simulation (looks up every risk linked
  to a scenario, requires each to already have its own config — raising rather than silently
  running a partial portfolio when one is missing — then delegates to the engine's
  correlation logic). Mirrors the `report_generate.py`/`packages.reporting` split from
  Milestone 5: the worker job owns status transitions, this module owns the actual work.
- **Simulations API** (`apps/api/app/routers/simulations.py`): `POST /api/v1/simulations`
  creates a config *and* enqueues its run in one call (matching the API design doc's "create
  config + enqueue run" phrasing exactly, rather than a separate config-then-run round trip);
  `GET /api/v1/simulations/{id}` for status + results; `GET /api/v1/simulations?risk_id=` for
  a risk's run history; `POST /api/v1/simulations/portfolio` for a scenario's portfolio run.
  All dispatched to `apps/worker` via the JobQueue (ADR 0005), same as reporting.
- **Scenarios API** (`apps/api/app/routers/scenarios.py`): full CRUD plus
  `POST/DELETE /scenarios/{id}/risks/{risk_id}` for linking, and a read-only
  `GET /scenarios/{id}/exposure` reporting which linked risks are ready for a portfolio run
  and which are missing a config. The API design doc's exposure endpoint description says it
  "may trigger simulation" — deliberately not implemented that way: every simulation run in
  this platform is an explicit `POST`, never a side effect of a `GET`, consistent with every
  other action in the system (and with basic REST semantics). Triggering a run stays a
  separate, explicit call to `/simulations/portfolio`.
- **`apps/worker/app/jobs/simulation_run.py`**: loads the run, marks it `running`, dispatches
  to the single-risk or portfolio service function based on which FK is set, and — like
  Milestone 5's `report_generate.py` — explicitly marks the run `failed` with the error
  message before re-raising, since a `SimulationRun`'s status is directly user-visible on the
  Simulation Lab and Scenario pages.
- **RBAC**, matching `docs/api/00-api-design.md`'s matrix exactly: `RUN_OWN_SIMULATION` (Risk
  Owner, their own risks only — enforced the same ownership-check pattern as risk editing,
  not a blanket permission), `RUN_ANY_SIMULATION` (Risk Manager, Administrator — also the
  only roles that can trigger a *portfolio* run, since a scenario spans risks an individual
  owner doesn't necessarily own), `VIEW_SIMULATION_RESULTS` (Risk Owner, Risk Manager,
  Executive, Administrator — Auditor and Control Owner cannot view simulation results at all,
  per the matrix), `MANAGE_SCENARIOS` (Risk Manager, Administrator).

### Frontend
- **`/simulations`** (Simulation Lab): pick a risk from a dropdown (URL carries
  `?risk_id=` so the risk detail page's new "Run Monte Carlo simulation" link opens straight
  into it), configure distribution/loss estimates/frequency/iterations/seed, run, and watch
  the run poll from Pending → Succeeded automatically. Results render as KPI tiles (expected
  annual loss, median, P90/P95/P99) plus a Recharts histogram of the simulated annual loss
  distribution, with full run history below. The configure-and-run panel only renders for a
  role that can actually run a simulation for the selected risk (mirroring the API's own
  ownership check client-side for UX, never trusted as the real gate).
- **`/scenarios`** (list + create, Risk Manager/Administrator) and **`/scenarios/[id]`**
  (detail): link/unlink risks, see which linked risks still need their own simulation config
  before a portfolio run can succeed (with a direct link into the Simulation Lab to fix it),
  trigger a portfolio run, and see the same KPI/histogram treatment as a single-risk run plus
  a Tail-Risk Contribution table ranking each linked risk's share of the worst-5% outcomes.

### Seed data
`database/seed/seed.py` gained `seed_demo_simulations()`, following the same
per-entity-idempotency pattern established for every prior milestone's seed additions
(checks its own table's existence, independent of whatever else has or hasn't been seeded).
Unlike Milestone 4's necessarily-fabricated historical snapshot (no real history existed to
compute from), this seed function's *loss estimates* are illustrative fabrication in the same
spirit as the fixture spreadsheet, but its *results* are not fabricated at all — the seed
script calls the real engine (`run_annual_loss_simulation`, `run_portfolio_simulation`) at
seed time, the same code a live run executes, and persists genuine computed output. Seeds
three configs (`RSK-1002` Unpatched internet-facing servers — PERT; `RSK-1001` Single-sourced
payment processor outage — Lognormal; `RSK-1004` Upcoming data-residency regulation —
Triangular, uncorrelated) each with an already-completed run, plus a demo scenario
correlating the first two under a shared `cyber-cluster` correlation group with its own
completed portfolio run — so the Simulation Lab and Scenarios pages both have real,
non-empty, non-fabricated results immediately after `docker compose up`.

## Tests

- 29 `packages/simulations` unit tests: distribution samplers (bounds, determinism, PERT's
  tighter concentration than Triangular around the same mode), Poisson (zero-mean is always
  zero, sample mean converges to the parameter), the annual-loss engine (deterministic given
  a seed, zero frequency means zero loss every year, higher frequency raises expected loss),
  percentile ordering, `correlate_series` (preserves the exact value multiset, matches the
  reference's rank order), and — the test that actually proves correlation works, not just
  compiles — a correlated pair's measured Pearson correlation exceeding an otherwise-identical
  independent pair's.
- 8 `packages/shared`/`apps/worker` tests covering the service layer's defensive checks
  (a config that doesn't exist, a scenario with no linked risks) and the worker job handler
  end-to-end for both a single-risk run and a correlated two-risk portfolio run (asserting
  the persisted result's tail contributions sum to 1).
- 25 `apps/api` integration tests: full RBAC matrix for requesting a simulation (Risk Owner
  on their own vs. someone else's risk, Control Owner forbidden, Risk Manager/Administrator
  on any risk, Executive forbidden to run but implicitly allowed to view), run lifecycle
  (succeeds after processing, reproducible given the same seed, 404s, view-permission
  enforcement), portfolio RBAC and the missing-config failure path, and full scenario CRUD +
  risk linking (idempotent) + exposure reporting.

**300 pytest tests, all passing** (up from 235). Frontend verified via `npx tsc --noEmit` and
`npm run build` (both clean, `/simulations` and `/scenarios[/[id]]` present in the route
manifest — `/simulations` uses `useSearchParams`, which Next.js requires wrapping in a
`Suspense` boundary for static prerendering, done here and confirmed by the clean build), plus
a full live-stack Playwright pass: ran a single-risk simulation and watched Pending →
Succeeded via the page's own polling with a realistic right-skewed loss histogram rendering
correctly; configured two risks with a shared correlation group, linked them to a scenario,
ran the portfolio simulation, and confirmed the Tail-Risk Contribution table showed a
sensible, non-50/50 split reflecting the two risks' actually different loss distributions.

## Bugs found and fixed during verification

- **Portfolio result never appeared in a Playwright run that also created single-risk
  configs beforehand.** The JobQueue processes one job at a time, oldest first; a test/manual
  flow that creates two single-risk configs (each enqueuing its own run) and *then* triggers
  a portfolio run has three jobs queued, but calling the worker's `process_one()` only once
  only drains the oldest (a single-risk run), not the portfolio run — the portfolio run
  stayed `pending`. This surfaced first as a failing API test, not a live-stack issue (the
  live demo's worker polls continuously and drains its own queue automatically); fixed the
  test to drain the queue in a loop rather than assuming one job means one `process_one()`
  call. Documented here because it's a real property of the architecture worth knowing when
  writing any test or script against it, not just a test bug to forget about.
- **`ScenarioHasNoLinkedRisksError` had no descriptive message** — its `__init__` passed only
  the scenario's UUID to `Exception.__init__`, so the `SimulationRun.error` field a user would
  actually see on a failed portfolio run was just a bare UUID with no explanation. Caught
  while writing a test that asserted on the error text, not by manual review. Fixed to include
  a proper "scenario {id} has no linked risks" message, matching
  `RiskMissingSimulationConfigError`'s existing style.
- **`seed_demo_simulations()` returned `True` (misleadingly claiming something was seeded)
  even when zero risks existed to configure.** The function's final `return True` sat after
  the risk-lookup loop unconditionally, so an empty database (or one where the three target
  fixture risk codes didn't exist) would still report success. Caught by a seed-script
  regression test (`test_skips_when_risks_do_not_exist_yet`) written to lock in the same
  "return value means something was actually created" contract every other seed function in
  this file follows. Fixed with an explicit `if not configs_by_code: return False` before the
  scenario section.
- **An empty PPTX table cell crashing on font styling** — not a new bug in this milestone,
  but worth noting the same defensive-check discipline from Milestone 5 (`report_generate`'s
  `IndexError` on an empty cell) was applied proactively here too: every new error path
  introduced in this milestone (`ScenarioHasNoLinkedRisksError`,
  `RiskMissingSimulationConfigError`, the config-not-found `ValueError`) has its own test
  asserting on the actual message text, not just that *an* exception was raised.

## Explicitly still deferred

- **Correlation is single-factor, not a full covariance matrix.** Risks in the same
  `correlation_group` all correlate through one shared systemic factor at each risk's own
  `correlation_strength` — this gives every pairwise correlation within a group the same
  general shape (roughly `strength_i × strength_j`), not an arbitrary user-specified
  correlation between any two specific risks. A full Gaussian-copula or covariance-matrix
  approach was considered and explicitly not built for this prototype (see the engine's
  module docstring) — the single-factor model is simpler, needs no distribution-specific
  inverse-CDF machinery, and is a defensible approximation for "these risks share an
  underlying cause" scenario narratives, which is what Milestone 7 actually asked for.
- **A risk can only belong to one correlation group per config.** If a risk should
  participate in two different systemic clusters simultaneously (e.g., both a "cyber" cluster
  and a "regional" cluster), that isn't representable — its `SimulationConfig` has exactly one
  `correlation_group` value.
- **No scenario-level financial/operational impact fields are used anywhere yet** — `Scenario`
  has `financial_impact_min/most_likely/max`, `operational_impact`, and
  `recovery_assumptions` columns (matching the domain model doc) that are captured on create
  but not yet rendered or reconciled against the portfolio simulation's own computed numbers.
  A future pass could show both side by side ("your rough estimate vs. what the model says").
- AI provider integration (Milestone 8), Emerging Risk Radar (9), MCP gateway (10), and GCP
  hardening (11) are unchanged.
