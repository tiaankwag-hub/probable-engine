# Risk Intelligence Platform

An enterprise Risk Intelligence Platform supporting the full risk lifecycle — Identify,
Assess, Control, Treat, Monitor, Escalate, Forecast, Report — replacing an earlier
Streamlit prototype with a production-grade, service-oriented architecture.

## Status: Milestone 0 — Architecture & Foundations

This repository was empty when this engagement began (no `legacy/` prototype or source
spreadsheet was present — see
[`docs/architecture/00-current-state-assessment.md`](docs/architecture/00-current-state-assessment.md)).
Milestone 0 establishes the architecture, ADRs, and repository skeleton; no application code
has been written yet.

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
database/        Alembic migrations, seed data
templates/       PPTX and PDF report templates
tests/           cross-cutting integration, RBAC, and Playwright end-to-end tests
infra/           Terraform modules and per-environment roots (dev/staging/production)
docs/            architecture, ADRs, API design, security
```

Every non-empty-yet directory above contains its own `README.md` explaining its purpose and
which milestone populates it.

## Delivery approach

Built as 11 vertical-slice milestones (see the roadmap linked above), each implemented,
tested, documented, and demonstrated before the next begins — not built all at once.

## Local development

Not available yet — begins in Milestone 1 with a Docker Compose stack (PostgreSQL, API,
worker, web) that requires no cloud credentials (AI and external signal sources use mock/
fixture providers locally).

## Production target

Google Cloud Run, Cloud SQL for PostgreSQL, Cloud Storage, Vertex AI/Gemini, and Terraform
(Milestone 11). This development environment is Mac-only and does not hold GCP credentials
or provision infrastructure; production deployment is performed from a separate corporate
Windows workstation via Git and GCP.
