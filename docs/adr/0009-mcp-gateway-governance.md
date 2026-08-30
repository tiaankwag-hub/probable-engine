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
