# apps/web

Next.js / TypeScript / React / Tailwind frontend for the Risk Intelligence Platform.

Responsibilities: rendering the Executive Dashboard, Risk Register, Risk Detail, Controls,
Actions, Governance Health, Heatmap, Trends, Simulation Lab, Scenarios, Emerging Risks,
Reports, and Administration pages, via a generated/typed API client against `apps/api`.

No business logic lives here — this app renders state and calls the API. Authoritative
scoring, RBAC enforcement, and workflow rules live in `apps/api` and `packages/`.

Status: Milestone 1-2 complete — Risk Register list/create/detail with in-place reassessment
and version history, the full Import Wizard UI, the Executive Dashboard (KPI tiles, 5×5
heatmap, category exposure and velocity charts via Recharts, top-risks list), and a
scoring-config administration page. Still built with plain Tailwind-styled elements rather
than shadcn/ui's Radix primitives (ADR 0003) — neither milestone's UI needed a dropdown or
dialog complex enough to justify introducing them yet; still expected whenever one does.
