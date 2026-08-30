# apps/web

Next.js / TypeScript / React / Tailwind frontend for the Risk Intelligence Platform.

Responsibilities: rendering the Executive Dashboard, Risk Register, Risk Detail, Controls,
Actions, Governance Health, Heatmap, Trends, Simulation Lab, Scenarios, Emerging Risks,
Reports, and Administration pages, via a generated/typed API client against `apps/api`.

No business logic lives here — this app renders state and calls the API. Authoritative
scoring, RBAC enforcement, and workflow rules live in `apps/api` and `packages/`.

Status: Milestone 1 complete — Risk Register list/create/detail with in-place reassessment
and version history, and the full Import Wizard UI. Built with plain Tailwind-styled
elements rather than shadcn/ui's Radix primitives (ADR 0003); that gap is intended to close
in Milestone 2 when dropdown/dialog-heavy UI actually needs them.
