# ADR 0001: Monorepo with apps/ and packages/ separation

## Status
Accepted

## Context
The platform ships four deployable services (web, api, worker, mcp) that share a domain
model, validation rules, and infrastructure adapters. Splitting into separate repositories
early risks schema/logic drift between services and slows iteration during Milestones 0–10
where the domain model is still evolving.

## Decision
Use a single repository with `apps/*` (deployable services) and `packages/*` (shared,
non-deployable domain/infra code): `risk_engine`, `reporting`, `simulations`, `ai`,
`shared`. `apps/api` and `apps/worker` both depend on `packages/*`; `apps/web` depends only
on the generated typed API client, never on Python packages.

## Consequences
- A single PR can change a domain rule and both consumers (API + worker) atomically.
- CI must scope test/build runs per changed path to keep pipeline time reasonable as the repo
  grows.
- Each `apps/*` service still builds its own container image; the monorepo does not imply a
  single deployable artifact.
- If the MCP gateway or worker later need independent release cadences at a much larger
  scale, this can be revisited — not a concern at current scope.
