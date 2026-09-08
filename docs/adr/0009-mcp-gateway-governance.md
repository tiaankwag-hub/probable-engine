# ADR 0009: MCP gateway as a governed, permissioned API client

## Status
Accepted

## Context
The brief requires an optional MCP gateway exposing risk-domain tools, explicitly
prohibiting unrestricted SQL or filesystem access and requiring that tools respect user
authorization and role permissions.

## Decision
`apps/mcp` is implemented as a thin service that translates each governed tool
(`get_risk`, `search_risks`, `run_monte_carlo`, `generate_executive_report`, etc.) into one
or more authenticated calls to `apps/api` — it holds no direct database connection and no
filesystem access beyond what any other API client would have. The caller's identity is
passed through and subject to the same RBAC checks as the REST API; there is no separate,
more-permissive credential for MCP.

## Consequences
- The tool surface is a fixed, reviewed allowlist; adding a tool means adding an API-backed
  handler, not opening a new access path.
- MCP cannot outpace API-level security fixes, since it has no independent data access.
- Implementation is deferred to Milestone 10, after the REST API and RBAC model are stable,
  so the gateway is built against a settled contract rather than a moving one.

## Status update — Milestone 10 (complete)

Built as `apps/mcp`, its own service with its own dependency set (see
`docs/architecture/milestone-10-plan.md`). Identity is established the same way this ADR
describes: `RiskPlatformTokenVerifier` resolves a caller's bearer token by calling apps/api's
`GET /api/v1/auth/me` — the gateway has no independent notion of "who is this" and no OAuth
authorization server of its own. Nine tools shipped (`get_risk`, `search_risks`,
`get_top_risks`, `get_executive_dashboard`, `get_governance_health`, `run_monte_carlo`,
`get_simulation_run`, `generate_executive_report`, `get_report_run`), each a thin wrapper
around one existing REST route, verified live to pass RBAC decisions through unmodified
(a `viewer` token gets the identical 403 from a tool call that a REST call would return).
