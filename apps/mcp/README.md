# apps/mcp

Governed MCP gateway exposing a tightly-scoped, read-mostly set of risk-domain tools
(`get_risk`, `search_risks`, `get_top_risks`, `get_executive_dashboard`,
`get_governance_health`, `run_monte_carlo`, `get_simulation_run`,
`generate_executive_report`, `get_report_run`) to approved MCP clients.

Every tool call is authenticated and authorized against the same RBAC model as `apps/api`
(ADR 0009) — the gateway is a thin, permissioned client of the API, never talks to the
database directly, and never executes arbitrary SQL or filesystem access. See
`docs/architecture/milestone-10-plan.md` for what was built and how it was verified.

## Why this has its own `requirements.txt`

`apps/api`/`apps/worker` share the root `requirements.txt` and pin FastAPI to a Starlette
range the official `mcp` SDK's Streamable HTTP transport doesn't fit. Rather than force a
shared pin, `apps/mcp` gets its own isolated dependency set and its own container image
(ADR 0001 already allows this: each `apps/*` service builds its own image). It imports
nothing from `packages/*`.

## Local development

```bash
cd apps/mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# apps/api must already be running (e.g. via docker compose, or
# `uvicorn apps.api.app.main:app` from the repo root) — the gateway has
# nothing to serve without it.
PYTHONPATH=<repo-root> uvicorn apps.mcp.app.main:app --host 0.0.0.0 --port 8080
```

Point any MCP client (Streamable HTTP transport) at `http://localhost:8080/mcp` with
`Authorization: Bearer <token>` set to the same bearer token you'd send to `apps/api`
directly (e.g. the `access_token` from `POST /api/v1/auth/mock-login` in local dev).

## Tests

Run with the gateway's own venv — they need no database and no `apps/api` dependencies:

```bash
cd apps/mcp
source .venv/bin/activate
PYTHONPATH=<repo-root> python -m pytest tests/
```

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `MCP_API_BASE_URL` | `http://localhost:8000` | Where `apps/api` lives. |
| `MCP_IDENTITY_ISSUER_URL` | `http://localhost:8000` | Declarative only — surfaced in OAuth discovery metadata for MCP client tooling. Verification always goes through `apps/api`'s `/auth/me`, never this URL directly. Set to the real Google IAP/corporate SSO issuer in production. |
| `MCP_REQUEST_TIMEOUT_SECONDS` | `30` | Timeout for calls to `apps/api`. |
