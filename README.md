# Risk Intelligence Platform

An enterprise Risk Intelligence Platform supporting the full risk lifecycle — Identify,
Assess, Control, Treat, Monitor, Escalate, Forecast, Report — replacing an earlier
Streamlit prototype with a production-grade, service-oriented architecture.

## Status: Milestone 1 complete — Domain model, Risk Register, Import Wizard

This repository was empty when this engagement began (no `legacy/` prototype or source
spreadsheet was present — see
[`docs/architecture/00-current-state-assessment.md`](docs/architecture/00-current-state-assessment.md)).
Milestone 0 established the architecture, ADRs, and repository skeleton. Milestone 1 built
the PostgreSQL domain model, the deterministic risk-scoring engine, a working Risk Register
(FastAPI + Next.js) with server-enforced RBAC and full audit trail, and an end-to-end Import
Wizard against a synthetic fixture spreadsheet — see
[`docs/architecture/milestone-1-plan.md`](docs/architecture/milestone-1-plan.md) for exactly
what was built, what was tested, and where implementation deviated from the original plan.

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

Requires Docker and Docker Compose:

```bash
cp .env.example .env
docker compose up --build
# in another shell, once postgres is healthy:
docker compose exec api sh -c "cd apps/api && python -c 'from database.seed.seed import run; run()'"
```

Then open http://localhost:3000 and sign in as any seeded user (e.g.
`risk.manager@example.com`) — this is local mock authentication (ADR 0010), not a real login.

To run without Docker (e.g. for fast iteration): start a local PostgreSQL 16, then
`pip install -r requirements.txt`, `cd apps/api && alembic upgrade head`,
`python database/seed/seed.py`, `uvicorn apps.api.app.main:app --reload`, and in
`apps/worker`, `python -m apps.worker.app.main`; for the frontend, `cd apps/web && npm
install && npm run dev`. No cloud credentials are required — AI and external signal
sources will use mock/fixture providers once those milestones land.

### Tests

```bash
pip install -r requirements.txt && pytest              # 107 tests: risk_engine, shared, api, worker
cd tests/e2e && npm install && npx playwright test      # requires the full stack running
```

## Production target

Google Cloud Run, Cloud SQL for PostgreSQL, Cloud Storage, Vertex AI/Gemini, and Terraform
(Milestone 11). This development environment is Mac-only and does not hold GCP credentials
or provision infrastructure; production deployment is performed from a separate corporate
Windows workstation via Git and GCP.
