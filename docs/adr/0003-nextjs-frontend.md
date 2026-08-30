# ADR 0003: Next.js + TypeScript + Tailwind for the frontend

## Status
Accepted

## Context
The brief specifies Next.js/TypeScript/React/Tailwind with an enterprise component library
and a typed API client. The frontend must render dense executive dashboards, drill-down
detail views, and a multi-step Import Wizard without embedding business logic.

## Decision
Next.js (App Router) + TypeScript + Tailwind, with a typed client generated from the FastAPI
OpenAPI schema (e.g. `openapi-typescript` + a thin fetch wrapper). Component library choice
(e.g. a headless/accessible base such as Radix + Tailwind, rather than a full opinionated
design system) is deferred to Milestone 1 implementation so it can be validated against the
actual dashboard density requirements.

## Consequences
- All computed values shown in the UI (scores, bands, appetite flags, priority rank) come
  from the API — the frontend never recomputes them, avoiding logic drift.
- Accessibility (severity color contrast, keyboard navigation) is a first-class constraint
  for the component library choice, not an afterthought.
- Server components are used for data-heavy dashboard pages where feasible to reduce
  client-side bundle size; client components are reserved for interactive elements (Import
  Wizard steps, filters, the Simulation Lab).
