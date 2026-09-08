"""Builds the MCP gateway's ASGI app (ADR 0009). Composition, not
invention: FastMCP's Streamable HTTP transport plus a `TokenVerifier` that
delegates every identity check to apps/api. No OAuth authorization server
is implemented or impersonated here — `auth_server_provider` is never set,
so FastMCP adds no `/authorize`/`/token` endpoints; the only auth-related
addition to the route table is the Bearer-token enforcement wrapper around
the MCP endpoint itself.
"""

from __future__ import annotations

from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from pydantic import AnyHttpUrl
from starlette.applications import Starlette

from apps.mcp.app.auth import RiskPlatformTokenVerifier
from apps.mcp.app.config import Settings, get_settings
from apps.mcp.app.tools import register_tools


def build_mcp_server(settings: Settings | None = None) -> FastMCP:
    settings = settings or get_settings()

    mcp = FastMCP(
        name="risk-intelligence-platform",
        instructions=(
            "Governed, read-mostly tools over the Risk Intelligence Platform. "
            "Every call runs under the caller's own identity and permissions — "
            "nothing here can read or do more than the same user could through "
            "the web app."
        ),
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(settings.identity_issuer_url),
            required_scopes=[],
            # Explicitly opting out of Protected Resource Metadata: this
            # gateway is an internal client of apps/api behind the same
            # trust boundary as the web app, not a public-facing OAuth
            # resource server that needs to advertise discovery metadata.
            resource_server_url=None,
        ),
        token_verifier=RiskPlatformTokenVerifier(settings),
    )
    register_tools(mcp, settings)
    return mcp


def build_app(settings: Settings | None = None) -> Starlette:
    return build_mcp_server(settings).streamable_http_app()
