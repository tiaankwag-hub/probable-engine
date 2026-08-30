# Delivery Roadmap

Vertical slices, in order. A milestone is not "done" until it has been implemented, tested,
documented, demonstrated, and is stable — the next milestone does not start early.

| # | Milestone | Delivers |
|---|---|---|
| 0 | Architecture & foundations | Architecture assessment, repo skeleton, ADRs, threat model, API/data-model design (this document set). |
| 1 | Domain model + Risk Register + Import Wizard | PostgreSQL schema (core tables), Alembic migrations, Risk Register CRUD API + UI, Import Wizard end-to-end, RBAC skeleton, audit events, Docker Compose, pytest + API integration tests. |
| 2 | Deterministic risk engine + dashboard + heatmap | `packages/risk_engine` scoring (impact/inherent/residual/bands), scoring config admin, Executive Dashboard core KPIs, 5x5 heatmap. |
| 3 | Controls + actions + governance health + appetite | Controls & control tests CRUD, risk↔control links, actions with overdue detection, risk appetite config + flagging, Governance Health page. |
| 4 | Snapshots + What Changed + trends | Snapshot capture job, current-vs-previous comparison, "What Changed?" view, trend charts. |
| 5 | PowerPoint/PDF reporting | `packages/reporting`, PPTX (1-slide, 2-slide ELT) and PDF templates, async report generation, Reports page. |
| 6 | Risk-level Monte Carlo | `packages/simulations` single-risk engine (Triangular/PERT/Lognormal), async job execution, Simulation Lab UI, reproducible seeded runs. |
| 7 | Scenario analysis + portfolio Monte Carlo | Scenario entities, portfolio simulation with correlation, tail-risk contribution, Scenarios page. |
| 8 | AI provider integration | `packages/ai` abstraction, mock + Vertex Gemini providers, analyst personas, AI suggestion review workflow. |
| 9 | Emerging Risk Radar | Signal adapters (fixtures first), classification/taxonomy mapping pipeline, candidate lifecycle, Emerging Risks page. |
| 10 | MCP gateway | `apps/mcp` governed tool surface over the stable API/RBAC model. |
| 11 | GCP deployment hardening | Terraform for Cloud Run/Cloud SQL/Cloud Storage/Secret Manager/Cloud Tasks/Cloud Scheduler/IAM, CI scanning gates, production readiness review. Executed from the separate corporate workstation. |

## Cross-cutting, present from Milestone 1 onward

- Structured logging with correlation/request/job/simulation/AI run IDs.
- Server-side RBAC enforcement and a role/access test suite that grows with every new route.
- Immutable audit events on every authoritative write.
- No business logic in route handlers or React components — it lives in `packages/*`.

## Explicitly deferred to Milestone 11 (not before)

GCP project configuration, IAM bindings, Cloud SQL/Cloud Run provisioning, Terraform apply,
Secret Manager population with real secrets, and any production credential handling. This
development environment does not perform any of these at any earlier milestone.
