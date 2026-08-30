# ADR 0003: Next.js + TypeScript + Tailwind for the frontend

## Status
Accepted

## Context
The brief specifies Next.js/TypeScript/React/Tailwind with an enterprise component library
and a typed API client. The frontend must render dense executive dashboards, drill-down
detail views, and a multi-step Import Wizard without embedding business logic.

## Decision
Next.js (App Router) + TypeScript + Tailwind, with a typed client generated from the FastAPI
OpenAPI schema (`openapi-typescript` + a thin fetch wrapper).

**Component library: shadcn/ui** (Radix UI primitives + Tailwind, components copied into
`apps/web/components/ui` rather than pulled in as an opaque npm dependency). Chosen over a
full opinionated design system (e.g. MUI, Ant Design) for four reasons specific to this
platform:
- **Accessibility for free** — Radix primitives ship correct keyboard navigation, focus
  management, and ARIA semantics, which the brief calls out explicitly (severity heatmaps,
  data tables, multi-step wizards all need this).
- **Density control** — dashboard and risk-register views need tight, enterprise-appropriate
  density; shadcn/ui components are unstyled-by-default primitives we compose, not a fixed
  visual language we fight against.
- **No runtime lock-in** — components live in our own tree, so severity-color tokens, table
  density, and chart integration (heatmap, trend charts) are ordinary Tailwind edits, not
  theme-override archaeology in a third-party package.
- **Ecosystem fit** — pairs directly with Tailwind (already chosen) and is the de facto
  standard for new enterprise Next.js/TypeScript apps as of 2026, minimizing onboarding cost.

Charting (heatmap, trend lines, exceedance curves) uses a lightweight, composable library
(Recharts) layered on top of shadcn/ui's styling rather than a separate charting suite.

## Consequences
- All computed values shown in the UI (scores, bands, appetite flags, priority rank) come
  from the API — the frontend never recomputes them, avoiding logic drift.
- Accessibility (severity color contrast, keyboard navigation) is inherited from Radix
  primitives and verified per-component, not an afterthought.
- Server components are used for data-heavy dashboard pages where feasible to reduce
  client-side bundle size; client components are reserved for interactive elements (Import
  Wizard steps, filters, the Simulation Lab).
- Because shadcn/ui components are copied in rather than installed, upgrading a component's
  base behavior is a deliberate, reviewed diff — not a silent transitive dependency bump.
