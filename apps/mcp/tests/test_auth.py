import httpx
import pytest

from apps.mcp.app.auth import RiskPlatformTokenVerifier
from apps.mcp.app.config import Settings


def _verifier(handler) -> RiskPlatformTokenVerifier:
    settings = Settings(api_base_url="http://apps-api.test")
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url=settings.api_base_url
    )
    return RiskPlatformTokenVerifier(settings, client=client)


@pytest.mark.asyncio
async def test_valid_token_resolves_to_an_access_token_carrying_roles_as_scopes():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/auth/me"
        assert request.headers["authorization"] == "Bearer good-token"
        return httpx.Response(200, json={"email": "rm@example.com", "roles": ["risk_manager"]})

    result = await _verifier(handler).verify_token("good-token")

    assert result is not None
    assert result.token == "good-token"
    assert result.client_id == "rm@example.com"
    assert result.scopes == ["risk_manager"]


@pytest.mark.asyncio
async def test_apps_api_401_means_no_access_token():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "unknown user"})

    assert await _verifier(handler).verify_token("bad-token") is None


@pytest.mark.asyncio
async def test_apps_api_unreachable_means_no_access_token_not_a_crash():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    assert await _verifier(handler).verify_token("any-token") is None
