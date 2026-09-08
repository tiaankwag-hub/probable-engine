"""The MCP gateway's tool surface (ADR 0009): a fixed, reviewed allowlist.
Every tool is a thin, read-mostly wrapper around one existing apps/api
route — no raw SQL, no filesystem path, no tool that can do anything a
REST client couldn't already do with the same token. Adding a tool means
adding a handler here that calls an existing endpoint, never opening a new
access path of its own.

Each tool pulls the caller's verified token via `get_access_token()`
(set by the auth middleware in server.py from the incoming Authorization
header) and forwards that exact token to apps/api — so RBAC is enforced
exactly once, by apps/api, for every tool call.
"""

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.fastmcp import FastMCP

from apps.mcp.app.api_client import RiskPlatformAPIError, RiskPlatformClient
from apps.mcp.app.config import Settings


class NotAuthenticatedError(Exception):
    """Raised if a tool is somehow invoked without a verified token having
    been attached to the request — should be unreachable in practice since
    RequireAuthMiddleware (server.py) rejects such requests before any tool
    handler runs, but a tool must never silently proceed as anonymous."""


def _client(settings: Settings) -> RiskPlatformClient:
    access_token = get_access_token()
    if access_token is None:
        raise NotAuthenticatedError("no verified caller identity for this request")
    return RiskPlatformClient(settings, token=access_token.token)


def _as_tool_error(exc: RiskPlatformAPIError) -> dict:
    return {"error": True, "status_code": exc.status_code, "detail": exc.detail}


def register_tools(mcp: FastMCP, settings: Settings) -> None:
    @mcp.tool()
    async def get_risk(risk_id: str) -> dict:
        """Fetch full detail for one risk by ID, including its current
        assessment, controls, actions, issues, and incidents."""
        try:
            return await _client(settings).get_risk(risk_id)
        except RiskPlatformAPIError as exc:
            return _as_tool_error(exc)

    @mcp.tool()
    async def search_risks(
        query: str | None = None,
        status: str | None = None,
        category_id: str | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> list:
        """Search/list risks by free-text title/code match, status
        (draft/active/closed/etc.), and/or category. Paginated."""
        try:
            return await _client(settings).search_risks(query, status, category_id, page, page_size)
        except RiskPlatformAPIError as exc:
            return [_as_tool_error(exc)]

    @mcp.tool()
    async def get_top_risks(limit: int = 10) -> list:
        """The highest-residual-score risks on the register right now, as
        already ranked by the Executive Dashboard."""
        try:
            dashboard = await _client(settings).get_executive_dashboard()
        except RiskPlatformAPIError as exc:
            return [_as_tool_error(exc)]
        return dashboard.get("top_risks", [])[:limit]

    @mcp.tool()
    async def get_executive_dashboard() -> dict:
        """Full executive dashboard: KPIs, heatmap, category exposure, and
        top risks."""
        try:
            return await _client(settings).get_executive_dashboard()
        except RiskPlatformAPIError as exc:
            return _as_tool_error(exc)

    @mcp.tool()
    async def get_governance_health() -> dict:
        """Governance health metrics: risks outside appetite, weak
        controls, overdue actions."""
        try:
            return await _client(settings).get_governance_health()
        except RiskPlatformAPIError as exc:
            return _as_tool_error(exc)

    @mcp.tool()
    async def run_monte_carlo(
        risk_id: str,
        distribution_type: str,
        loss_min: float,
        loss_most_likely: float,
        loss_max: float,
        annual_event_frequency: float = 1.0,
        iterations: int = 10_000,
        seed: int = 42,
    ) -> dict:
        """Enqueue a risk-level Monte Carlo simulation (Triangular/PERT/
        Lognormal). Runs asynchronously — returns a run with status
        'queued'/'running'; poll get_simulation_run for the result."""
        try:
            return await _client(settings).run_monte_carlo(
                risk_id,
                distribution_type,
                loss_min,
                loss_most_likely,
                loss_max,
                annual_event_frequency,
                iterations,
                seed,
            )
        except RiskPlatformAPIError as exc:
            return _as_tool_error(exc)

    @mcp.tool()
    async def get_simulation_run(run_id: str) -> dict:
        """Check the status/result of a previously started simulation run."""
        try:
            return await _client(settings).get_simulation_run(run_id)
        except RiskPlatformAPIError as exc:
            return _as_tool_error(exc)

    @mcp.tool()
    async def generate_executive_report(report_format: str, template: str = "one_slide") -> dict:
        """Enqueue generation of an executive report. report_format is
        'pdf' or 'powerpoint'; template ('one_slide' or 'two_slide_elt')
        only applies to powerpoint. Runs asynchronously — poll
        get_report_run for the result and download link."""
        try:
            return await _client(settings).generate_executive_report(report_format, template)
        except RiskPlatformAPIError as exc:
            return _as_tool_error(exc)

    @mcp.tool()
    async def get_report_run(run_id: str) -> dict:
        """Check the status of a previously requested report and get its
        download URL once ready."""
        try:
            return await _client(settings).get_report_run(run_id)
        except RiskPlatformAPIError as exc:
            return _as_tool_error(exc)
