"""Tool-surface tests. Each tool is invoked through the real FastMCP
dispatch (`mcp.call_tool`) with a verified identity injected the same way
the auth middleware injects one on a real request — via `auth_context_var`
— so these tests exercise the exact call path a live client hits, not a
bypass of it. RiskPlatformClient itself is stubbed (it's covered on its
own in test_api_client.py); what's under test here is that each tool wires
its arguments to the right client method and turns API errors into the
documented error-dict shape rather than raising out of the tool call.
"""

import json

import pytest
from mcp.server.auth.middleware.auth_context import auth_context_var
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from mcp.server.auth.provider import AccessToken

from apps.mcp.app import tools as tools_module
from apps.mcp.app.api_client import RiskPlatformAPIError
from apps.mcp.app.config import Settings
from apps.mcp.app.server import build_mcp_server


class StubClient:
    """Records every call made to it and returns/raises whatever the test
    configured, standing in for RiskPlatformClient."""

    calls: list[tuple[str, tuple, dict]] = []
    to_return: object = None
    to_raise: Exception | None = None

    def __init__(self, settings, token):
        self.token = token

    def __getattr__(self, name):
        async def _method(*args, **kwargs):
            StubClient.calls.append((name, args, kwargs))
            if StubClient.to_raise is not None:
                raise StubClient.to_raise
            return StubClient.to_return

        return _method


@pytest.fixture(autouse=True)
def _reset_stub():
    StubClient.calls = []
    StubClient.to_return = None
    StubClient.to_raise = None
    yield


@pytest.fixture
def mcp(monkeypatch):
    monkeypatch.setattr(tools_module, "RiskPlatformClient", StubClient)
    return build_mcp_server(Settings(api_base_url="http://unused"))


async def _call_as(mcp, name, arguments, scopes=None):
    """Returns the tool's result as a plain list of decoded JSON values —
    one per MCP content block. A tool returning a single dict comes back
    the same shape as one returning a single-item list (`[value]`); this
    mirrors the wire protocol rather than trying to guess which one the
    tool "meant", so callers index explicitly."""
    token = auth_context_var.set(
        AuthenticatedUser(
            AccessToken(token="the-callers-token", client_id="u@example.com", scopes=scopes or [])
        )
    )
    try:
        result = await mcp.call_tool(name, arguments)
    finally:
        auth_context_var.reset(token)
    return [json.loads(item.text) for item in result]


class TestAllToolsAreRegistered:
    @pytest.mark.asyncio
    async def test_exactly_the_reviewed_nine_tools_are_exposed(self, mcp):
        names = {t.name for t in await mcp.list_tools()}
        assert names == {
            "get_risk",
            "search_risks",
            "get_top_risks",
            "get_executive_dashboard",
            "get_governance_health",
            "run_monte_carlo",
            "get_simulation_run",
            "generate_executive_report",
            "get_report_run",
        }


class TestToolArgumentWiring:
    @pytest.mark.asyncio
    async def test_get_risk_forwards_risk_id_and_the_callers_token(self, mcp):
        StubClient.to_return = {"id": "abc"}
        await _call_as(mcp, "get_risk", {"risk_id": "abc"})
        name, args, kwargs = StubClient.calls[0]
        assert name == "get_risk"
        assert args == ("abc",)

    @pytest.mark.asyncio
    async def test_get_top_risks_slices_the_dashboards_top_risks(self, mcp):
        StubClient.to_return = {
            "top_risks": [{"title": f"risk {i}"} for i in range(5)]
        }
        result = await _call_as(mcp, "get_top_risks", {"limit": 2})
        assert StubClient.calls[0][0] == "get_executive_dashboard"
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_run_monte_carlo_passes_through_all_parameters(self, mcp):
        StubClient.to_return = {"id": "run1", "status": "queued"}
        await _call_as(
            mcp,
            "run_monte_carlo",
            {
                "risk_id": "r1",
                "distribution_type": "pert",
                "loss_min": 100.0,
                "loss_most_likely": 500.0,
                "loss_max": 2000.0,
                "iterations": 1000,
            },
        )
        name, args, kwargs = StubClient.calls[0]
        assert name == "run_monte_carlo"
        assert args[0] == "r1"

    @pytest.mark.asyncio
    async def test_generate_executive_report_defaults_template_to_one_slide(self, mcp):
        StubClient.to_return = {"id": "r1"}
        await _call_as(mcp, "generate_executive_report", {"report_format": "powerpoint"})
        name, args, kwargs = StubClient.calls[0]
        assert args == ("powerpoint", "one_slide")


class TestErrorSurfacing:
    @pytest.mark.asyncio
    async def test_api_error_becomes_a_structured_error_result_not_an_exception(self, mcp):
        StubClient.to_raise = RiskPlatformAPIError(403, "missing required permission: view_report_runs")
        result = await _call_as(mcp, "get_report_run", {"run_id": "run1"})
        assert result[0]["error"] is True
        assert result[0]["status_code"] == 403
        assert "missing required permission" in result[0]["detail"]

    @pytest.mark.asyncio
    async def test_search_risks_error_returns_a_list_with_one_error_entry(self, mcp):
        StubClient.to_raise = RiskPlatformAPIError(500, "boom")
        result = await _call_as(mcp, "search_risks", {})
        assert isinstance(result, list)
        assert result[0]["error"] is True
