"""Identity verification for the MCP gateway (ADR 0009).

There is deliberately no MCP-specific auth mechanism here — no issuer, no
token minting, no independent notion of "who is this". A caller presents
the same bearer token it would send straight to apps/api (a real IAP/SSO
identity token in production, the mock-auth UUID in local dev), and
`RiskPlatformTokenVerifier` confirms it the only way that respects ADR 0009:
by asking apps/api itself, via `GET /api/v1/auth/me`. If apps/api doesn't
recognize the token, the gateway doesn't either — there is no path for the
gateway to accept a token apps/api would reject, or vice versa.

The verified token's *own text* becomes `AccessToken.token`, so every tool
call forwards that exact same token to apps/api and rides the same RBAC
checks as any other API client. Roles resolved here are surfaced as MCP
scopes purely for logging/introspection — enforcement never happens in this
process, only in apps/api.

This call needs the same dual-header treatment as api_client.py's
RiskPlatformClient (see that module's docstring): in production, apps/api's
own Cloud Run ingress requires an IAM-authorized caller before this
gateway's request even reaches app code, which is a platform-level check
entirely separate from "is this token a valid human identity" — so
Authorization here carries this gateway's own service identity (falling
back to the caller's token off Cloud Run, where that check doesn't exist),
while the caller's token itself always rides X-Goog-IAP-JWT-Assertion,
which is what apps/api's app code actually verifies.
"""

from __future__ import annotations

import httpx
from mcp.server.auth.provider import AccessToken, TokenVerifier

from apps.mcp.app.api_client import service_identity_token
from apps.mcp.app.config import Settings


class RiskPlatformTokenVerifier(TokenVerifier):
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self._settings = settings
        self._client = client

    async def verify_token(self, token: str) -> AccessToken | None:
        client = self._client or httpx.AsyncClient(
            base_url=self._settings.api_base_url, timeout=self._settings.request_timeout_seconds
        )
        owns_client = self._client is None
        service_token = service_identity_token(audience=self._settings.api_base_url)
        headers = {
            "Authorization": f"Bearer {service_token or token}",
            "X-Goog-IAP-JWT-Assertion": token,
        }
        try:
            response = await client.get("/api/v1/auth/me", headers=headers)
        except httpx.HTTPError:
            return None
        finally:
            if owns_client:
                await client.aclose()

        if response.status_code != 200:
            return None

        body = response.json()
        return AccessToken(token=token, client_id=body["email"], scopes=body["roles"])
