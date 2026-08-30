# apps/mcp

Optional MCP gateway exposing a tightly governed, read-mostly set of risk-domain tools
(`get_risk`, `search_risks`, `get_top_risks`, `run_monte_carlo`, `generate_executive_report`,
etc.) to approved MCP clients.

Every tool call is authenticated and authorized against the same RBAC model as `apps/api`
(the gateway is a thin, permissioned client of the API — it never talks to the database
directly and never executes arbitrary SQL or filesystem access).

Status: not yet implemented. Planned for Milestone 10, after the API surface and RBAC model
it depends on are stable.
