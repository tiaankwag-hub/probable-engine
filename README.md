# Risk Intelligence Platform

An enterprise Risk Intelligence Platform supporting the full risk lifecycle — Identify,
Assess, Control, Treat, Monitor, Escalate, Forecast, Report — replacing an earlier
Streamlit prototype with a production-grade, service-oriented architecture.

## Status: Milestone 9 complete — Emerging Risk Radar

This repository was empty when this engagement began (no `legacy/` prototype or source
spreadsheet was present — see
[`docs/architecture/00-current-state-assessment.md`](docs/architecture/00-current-state-assessment.md)).
Milestone 0 established the architecture, ADRs, and repository skeleton. Milestone 1 built
the PostgreSQL domain model, the deterministic risk-scoring engine, a working Risk Register
(FastAPI + Next.js) with server-enforced RBAC and full audit trail, and an end-to-end Import
Wizard against a synthetic fixture spreadsheet. Milestone 2 added the Executive Dashboard
(KPI tiles, 5×5 heatmap, category exposure, top-risks list) and a scoring-config admin UI.
Milestone 3 made Controls and Actions first-class entities, added deterministic risk-appetite
evaluation, and a Governance Health page. Milestone 4 added point-in-time Snapshots, a "What
Changed?" comparison view, trend charts, and Issues/Incidents (human-reviewed evidence that
can trigger a risk review, never a silent mutation). Milestone 5 added on-demand PDF and
PowerPoint (1-slide and 2-slide ELT board pack) reporting, rendered asynchronously by
`apps/worker` and downloaded from a new Reports page. Milestones 6-7 (delivered together)
added a frequency-severity Monte Carlo engine for single-risk quantification and a scenario
analysis layer that runs the same engine across every risk linked to a scenario, correlating
those that share an underlying cause and reporting each risk's share of the tail outcomes.
Milestone 8 added a provider-neutral AI abstraction (`packages/ai`) with mandatory human
review — a deterministic mock provider for local dev/CI and a fully functional Google Gemini
API provider for real executive summaries, per-risk analysis, control-gap analysis,
emerging-risk scanning, and market/industry commentary today, built so that swapping in the
company's own Vertex AI/Gemini provider on GCP is a one-file addition, not a rewrite.
Milestone 9 added the Emerging Risk Radar: two fixture signal adapters standing in for a real
news/regulatory feed, a deterministic taxonomy classifier, an AI triage capability that turns
a classified signal into a review candidate, and a human-only lifecycle that can accept a
candidate into a real risk (always with a placeholder, unrated assessment), link it to one
already on file, or dismiss it — see
[`docs/architecture/milestone-1-plan.md`](docs/architecture/milestone-1-plan.md),
[`docs/architecture/milestone-2-plan.md`](docs/architecture/milestone-2-plan.md),
[`docs/architecture/milestone-3-plan.md`](docs/architecture/milestone-3-plan.md),
[`docs/architecture/milestone-4-plan.md`](docs/architecture/milestone-4-plan.md),
[`docs/architecture/milestone-5-plan.md`](docs/architecture/milestone-5-plan.md),
[`docs/architecture/milestone-6-7-plan.md`](docs/architecture/milestone-6-7-plan.md),
[`docs/architecture/milestone-8-plan.md`](docs/architecture/milestone-8-plan.md), and
[`docs/architecture/milestone-9-plan.md`](docs/architecture/milestone-9-plan.md) for
exactly what was built, tested, and where implementation deviated from the original plan.
Post-Milestone-9 enhancements (a downloadable import template, a redesigned left-sidebar UI, a
deeper Executive Summary with risk-tolerance sliders, and Guided Risk Intake — a chat-driven
alternative to the manual "New Risk" form for non-expert users and executives, always landing
as a `draft` for a Risk Manager to review) are documented at the end of
[`docs/architecture/milestone-1-plan.md`](docs/architecture/milestone-1-plan.md).

## Start here

| Topic | Document |
|---|---|
| What was found when this repo was inspected | [`docs/architecture/00-current-state-assessment.md`](docs/architecture/00-current-state-assessment.md) |
| Target architecture, diagrams, sync/async boundaries, dev-vs-prod mapping | [`docs/architecture/01-target-architecture.md`](docs/architecture/01-target-architecture.md) |
| Domain model | [`docs/architecture/02-domain-model.md`](docs/architecture/02-domain-model.md) |
| ER diagram | [`docs/architecture/03-er-diagram.md`](docs/architecture/03-er-diagram.md) |
| API design | [`docs/api/00-api-design.md`](docs/api/00-api-design.md) |
| Security model & threat model | [`docs/security/threat-model.md`](docs/security/threat-model.md), [`SECURITY.md`](SECURITY.md) |
| Architecture decisions | [`docs/adr/`](docs/adr/README.md) |
| Full delivery roadmap (Milestones 0–11) | [`docs/architecture/roadmap.md`](docs/architecture/roadmap.md) |
| Milestone 1 implementation plan | [`docs/architecture/milestone-1-plan.md`](docs/architecture/milestone-1-plan.md) |
| Milestone 2 implementation plan | [`docs/architecture/milestone-2-plan.md`](docs/architecture/milestone-2-plan.md) |
| Milestone 3 implementation plan | [`docs/architecture/milestone-3-plan.md`](docs/architecture/milestone-3-plan.md) |
| Milestone 4 implementation plan | [`docs/architecture/milestone-4-plan.md`](docs/architecture/milestone-4-plan.md) |
| Milestone 5 implementation plan | [`docs/architecture/milestone-5-plan.md`](docs/architecture/milestone-5-plan.md) |
| Milestone 6-7 implementation plan | [`docs/architecture/milestone-6-7-plan.md`](docs/architecture/milestone-6-7-plan.md) |
| Milestone 8 implementation plan | [`docs/architecture/milestone-8-plan.md`](docs/architecture/milestone-8-plan.md) |
| Milestone 9 implementation plan | [`docs/architecture/milestone-9-plan.md`](docs/architecture/milestone-9-plan.md) |

## Repository layout

```
apps/            web (Next.js), api (FastAPI), worker, mcp — deployable services
packages/        risk_engine, reporting, simulations, ai, shared — shared domain/infra code
database/        Alembic migrations, seed data, the synthetic fixture spreadsheet
templates/       PPTX and PDF report templates
tests/e2e/       Playwright end-to-end specs
infra/           Terraform modules and per-environment roots (dev/staging/production)
docs/            architecture, ADRs, API design, security
```

Every directory above contains its own `README.md` explaining its purpose and which
milestone populates it.

## Delivery approach

Built as 11 vertical-slice milestones (see the roadmap linked above), each implemented,
tested, documented, and demonstrated before the next begins — not built all at once.

## Local development

**One command starts everything — frontend, API, PostgreSQL, and the worker:**

```bash
cp .env.example .env
docker compose up --build
```

That single command builds all four services, runs the database migrations, and seeds the
database automatically (roles, one user per role, starter categories, the scoring config,
20 synthetic demo risks, 6 controls, and ~20 actions derived from the same fixture) —
`database/seed/seed.py` is idempotent, so re-running `docker compose up` never duplicates
data. No GCP credentials or any cloud account are required for local development at any
milestone.

See **"Local demonstration"** in each milestone's plan doc
(e.g. [`docs/architecture/milestone-1-plan.md`](docs/architecture/milestone-1-plan.md)) for
the exact URL, features to test, seeded credentials, and stop command as of that milestone.

**Stop and remove everything:**

```bash
docker compose down          # stop, keep data
docker compose down -v       # stop and wipe the database/storage volumes
```

**Without Docker** (e.g. fast local iteration): start a local PostgreSQL 16, then
`pip install -r requirements.txt`, `cd apps/api && alembic upgrade head`,
`python database/seed/seed.py`, `uvicorn apps.api.app.main:app --reload`, and in a second
shell `python -m apps.worker.app.main`; for the frontend, `cd apps/web && npm install && npm
run dev`.

### Tests

```bash
pip install -r requirements.txt && pytest              # 186 tests: risk_engine, shared, api, worker
cd tests/e2e && npm install && npx playwright test      # 6 specs, requires the full stack running
```

## Production target

Google Cloud Run, Cloud SQL for PostgreSQL, Cloud Storage, Vertex AI/Gemini, and Terraform
(Milestone 11). This development environment is Mac-only and does not hold GCP credentials
or provision infrastructure; production deployment is performed from a separate corporate
Windows workstation via Git and GCP.
