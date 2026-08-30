# apps/web

Next.js / TypeScript / React / Tailwind frontend for the Risk Intelligence Platform.

Responsibilities: rendering the Executive Dashboard, Risk Register, Risk Detail, Controls,
Actions, Governance Health, Heatmap, Trends, Simulation Lab, Scenarios, Emerging Risks,
Reports, and Administration pages, via a generated/typed API client against `apps/api`.

No business logic lives here — this app renders state and calls the API. Authoritative
scoring, RBAC enforcement, and workflow rules live in `apps/api` and `packages/`.

Status: not yet implemented. First code lands in Milestone 1 (Risk Register CRUD + Import
Wizard UI).
