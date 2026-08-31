# Delivery Roadmap

Vertical slices, in order. A milestone is not "done" until it has been implemented, tested,
documented, demonstrated, and is stable — the next milestone does not start early.

| # | Milestone | Delivers |
|---|---|---|
| 0 | Architecture & foundations | Architecture assessment, repo skeleton, ADRs, threat model, API/data-model design (this document set). **Complete.** |
| 1 | Domain model + Risk Register + Import Wizard | PostgreSQL schema (core tables), Alembic migrations, Risk Register CRUD API + UI, Import Wizard end-to-end, RBAC skeleton, audit events, Docker Compose, pytest + API integration tests. **Complete** — see `docs/architecture/milestone-1-plan.md`. Also delivered the full deterministic scoring pipeline originally scoped for Milestone 2 (see that plan's "Deviations" section). |
| 2 | Dashboard + heatmap + scoring config admin | Executive Dashboard core KPIs, 5x5 heatmap, category exposure, scoring-config admin UI (the scoring engine itself shipped in Milestone 1). **Complete** — see `docs/architecture/milestone-2-plan.md`. Also retroactively added the structured logging/correlation-ID observability this document had (incorrectly) claimed since Milestone 0. Radix primitives (shadcn/ui) still not introduced — the dashboard's charts and admin form didn't need dialogs/comboboxes; still expected in Milestone 3's Governance Health page or wherever the first one is genuinely needed. |
| 3 | Controls + actions + governance health + appetite | Controls & control tests CRUD, risk↔control links, actions with overdue detection, risk appetite config + flagging, Governance Health page. **Complete** — see `docs/architecture/milestone-3-plan.md`. Also enriched the Executive Dashboard with the three KPIs Milestone 2 explicitly deferred (Risks Outside Appetite, Weak Controls, Overdue Actions). |
| 4 | Snapshots + What Changed + trends + Issues/Incidents | Snapshot capture, current-vs-previous comparison, "What Changed?" view, trend charts, Issues and Incidents (absorbed from the brief, which Milestone 0's roadmap never assigned a milestone to). **Complete** — see `docs/architecture/milestone-4-plan.md`. |
| 5 | PowerPoint/PDF reporting | `packages/reporting`, PPTX (1-slide, 2-slide ELT) and PDF templates, async report generation, Reports page. **Complete** — see `docs/architecture/milestone-5-plan.md`. |
| 6 | Risk-level Monte Carlo | `packages/simulations` single-risk engine (Triangular/PERT/Lognormal), async job execution, Simulation Lab UI, reproducible seeded runs. |
| 7 | Scenario analysis + portfolio Monte Carlo | Scenario entities, portfolio simulation with correlation, tail-risk contribution, Scenarios page. |
| 8 | AI provider integration | `packages/ai` abstraction, mock + Vertex Gemini providers, analyst personas, AI suggestion review workflow. |
| 9 | Emerging Risk Radar | Signal adapters (fixtures first), classification/taxonomy mapping pipeline, candidate lifecycle, Emerging Risks page. |
| 10 | MCP gateway | `apps/mcp` governed tool surface over the stable API/RBAC model. |
| 11 | GCP deployment hardening | Terraform for Cloud Run/Cloud SQL/Cloud Storage/Secret Manager/Cloud Tasks/Cloud Scheduler/IAM, CI scanning gates, production readiness review. Executed from the separate corporate workstation. |

## Cross-cutting, present from Milestone 1 onward

- Server-side RBAC enforcement and a role/access test suite that grows with every new route.
- Immutable audit events on every authoritative write.
- No business logic in route handlers or React components — it lives in `packages/*`.
- Structured logging with correlation/request/job IDs — actually landed in Milestone 2 (see
  that plan's Observability section), not Milestone 1 as an earlier version of this table
  claimed. Simulation/AI run IDs will extend the same mechanism when those milestones land.

## Explicitly deferred to Milestone 11 (not before)

GCP project configuration, IAM bindings, Cloud SQL/Cloud Run provisioning, Terraform apply,
Secret Manager population with real secrets, and any production credential handling. This
development environment does not perform any of these at any earlier milestone.
