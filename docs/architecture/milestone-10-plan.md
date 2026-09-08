# Milestone 10 Implementation Plan — COMPLETE

The MCP gateway: a governed tool surface over the stable API/RBAC model (ADR 0009), letting
approved MCP clients (Claude Desktop, Claude Code, or any other MCP-speaking tool) read the
risk register, dashboards, and run/report status, and enqueue a Monte Carlo simulation or a
report — all under the calling human's own identity and permissions, never a separate
credential.

## What was built

### `apps/mcp` (new service) — its own dependency world, deliberately
Unlike `apps/api`/`apps/worker`, which share the root `requirements.txt`, `apps/mcp` ships
its own `apps/mcp/requirements.txt` and builds its own container image (ADR 0001 already
anticipated this: "each `apps/*` service still builds its own container image"). This isn't
arbitrary — the official `mcp` Python SDK's Streamable HTTP transport needs a newer Starlette
than `apps/api`'s pinned FastAPI version tolerates; giving the gateway its own isolated
dependency set (and its own local venv for development/testing) sidesteps that conflict
entirely rather than forcing a shared pin. `apps/mcp` imports nothing from `packages/*` and
has no database URL, no storage root, no AI provider key in its settings — it *cannot* reach
any of those things even by mistake, which is the concrete enforcement of ADR 0009's "no
direct database connection, no filesystem access beyond what any other API client would have."

### Identity: no new auth mechanism, just a relay
- **`apps/api` gained one endpoint**: `GET /api/v1/auth/me`, returning the identity and roles
  `get_current_user` already resolves for any bearer token. This is the only change to
  `apps/api` this milestone needed.
- **`apps/mcp/app/auth.py`**: `RiskPlatformTokenVerifier` implements the `mcp` SDK's
  `TokenVerifier` protocol by calling `GET /api/v1/auth/me` with whatever token the caller
  presented. If apps/api doesn't recognize the token, neither does the gateway — there is no
  path for the two to disagree about who someone is, and no MCP-specific credential exists at
  all. The verified token's own text becomes the `AccessToken.token`, so it's the *same* token
  that gets forwarded on every subsequent tool call.
- **No OAuth authorization server is implemented or impersonated.** `auth_server_provider` is
  never set, so the SDK adds no `/authorize`/`/token`/discovery endpoints — this gateway is an
  internal client of `apps/api` behind the same trust boundary as the web app (per the threat
  model), not a public-facing OAuth resource server. The only auth-related addition to the
  route table is the Bearer-token enforcement wrapper the SDK provides
  (`BearerAuthBackend` + `AuthContextMiddleware` + `RequireAuthMiddleware`, composed as-is, not
  reimplemented) around the single `/mcp` endpoint.

### The tool surface: a fixed, reviewed allowlist of 9
`get_risk`, `search_risks`, `get_top_risks`, `get_executive_dashboard`,
`get_governance_health`, `run_monte_carlo`, `get_simulation_run`,
`generate_executive_report`, `get_report_run` — each one a thin wrapper (`api_client.py`)
around exactly one existing `apps/api` route. Every tool call:
1. Reads the verified caller identity via the SDK's `get_access_token()` (populated by the
   auth middleware from the incoming request, not by the tool itself).
2. Forwards that exact token to `apps/api`.
3. Returns whatever `apps/api` returns — including its 403s and 404s, surfaced as a structured
   `{"error": true, "status_code": ..., "detail": ...}` result rather than swallowed or
   retried with different credentials.

Nothing here can read or do more than the same human could already do through the web app.
Adding a 10th tool later means adding one more thin wrapper against an existing route, never
opening a new access path.

### Verified live, not just unit-tested
With `apps/api` running locally, started the gateway (`uvicorn apps.mcp.app.main:app`) and
drove it with the real `mcp` Python client SDK end-to-end:
- A request with no `Authorization` header → `401`, before any tool runs.
- A `risk_manager` login → `mcp list_tools()` shows all 9 tools; `get_top_risks` and
  `get_governance_health` return real data straight from the seeded database.
- A `viewer` login calling `get_report_run` → the gateway returns the same
  `403 missing required permission: view_report_runs` `apps/api` itself would give a REST
  client with that role, byte-for-byte — proving RBAC passes through unmodified rather than
  being re-decided (or accidentally loosened) inside the gateway.

### Tests (`apps/mcp/tests`, run with the gateway's own isolated venv)
17 tests: `test_auth.py` (token verification against a mocked apps/api — valid token, 401,
apps/api unreachable), `test_api_client.py` (every method's request shape, error-detail
parsing, the 204→`{}` case) using `httpx.MockTransport` wired into the client's *actual*
`_request` method rather than a reimplementation of it, and `test_tools.py` (all 9 tools
registered by name, argument wiring, and that a `RiskPlatformAPIError` becomes the documented
error dict instead of an exception) invoked through the real FastMCP `call_tool` dispatch with
a verified identity injected the same way the auth middleware injects one on a live request.

### Docker Compose
Added an `mcp` service (`apps/mcp/Dockerfile`, its own image) pointed at `api` over the
compose network; not published on a host port by default, matching "not exposed to the public
internet" — only approved MCP clients on the same network reach `http://mcp:8080/mcp`.

## Explicitly still deferred
- **Real OAuth/IAP-issued tokens** — local dev still authenticates through the same mock-auth
  UUID scheme every other route uses; wiring the identity issuer to real Google IAM/IAP or
  corporate SSO tokens is Milestone 11's concern, and requires no change to `apps/mcp` itself
  (`RiskPlatformTokenVerifier` already just forwards whatever token it's given to `apps/api`,
  which is where real token verification will actually happen).
- **`docker compose up --build` of the new `mcp` service** was not run in this environment (no
  Docker daemon available here this session) — validated instead by running the identical
  code path directly with `uvicorn` against a live `apps/api`, including the real MCP client
  round-trip described above. Confirming the container build itself is a fast, low-risk
  follow-up for whoever next has Docker available.
- **A download/binary-content tool** was deliberately not added — `get_report_run` returns a
  `download_url` once a report is ready, but fetching the rendered PDF/PPTX bytes through MCP
  itself was out of scope for a "read-mostly" gateway; that still goes through the web app.
