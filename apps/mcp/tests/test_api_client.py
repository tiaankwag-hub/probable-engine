import json

import httpx
import pytest

from apps.mcp.app import api_client as api_client_module
from apps.mcp.app.api_client import RiskPlatformAPIError, RiskPlatformClient
from apps.mcp.app.config import Settings


def _install_transport(monkeypatch, handler) -> None:
    """Makes every httpx.AsyncClient the real api_client.py code constructs
    use our mock transport instead of touching the network — so these tests
    exercise RiskPlatformClient's actual `_request` implementation, not a
    reimplementation of it."""
    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    class PatchedAsyncClient(real_async_client):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(api_client_module.httpx, "AsyncClient", PatchedAsyncClient)


@pytest.mark.asyncio
async def test_get_risk_forwards_the_bearer_token(monkeypatch):
    def handler(request):
        assert request.url.path == "/api/v1/risks/abc"
        assert request.headers["authorization"] == "Bearer tok"
        return httpx.Response(200, json={"id": "abc", "title": "Vendor risk"})

    _install_transport(monkeypatch, handler)
    client = RiskPlatformClient(Settings(api_base_url="http://apps-api.test"), token="tok")
    result = await client.get_risk("abc")
    assert result == {"id": "abc", "title": "Vendor risk"}


@pytest.mark.asyncio
async def test_search_risks_passes_filters_as_query_params(monkeypatch):
    def handler(request):
        assert request.url.path == "/api/v1/risks"
        assert request.url.params["q"] == "vendor"
        assert request.url.params["status"] == "active"
        assert request.url.params["page"] == "2"
        return httpx.Response(200, json=[])

    _install_transport(monkeypatch, handler)
    client = RiskPlatformClient(Settings(api_base_url="http://apps-api.test"), token="tok")
    await client.search_risks(query="vendor", status="active", page=2)


@pytest.mark.asyncio
async def test_run_monte_carlo_posts_expected_body(monkeypatch):
    def handler(request):
        assert request.url.path == "/api/v1/simulations"
        payload = json.loads(request.content)
        assert payload["risk_id"] == "r1"
        assert payload["distribution_type"] == "pert"
        assert payload["iterations"] == 5000
        return httpx.Response(202, json={"id": "run1", "status": "queued"})

    _install_transport(monkeypatch, handler)
    client = RiskPlatformClient(Settings(api_base_url="http://apps-api.test"), token="tok")
    result = await client.run_monte_carlo(
        risk_id="r1",
        distribution_type="pert",
        loss_min=1000,
        loss_most_likely=5000,
        loss_max=20000,
        iterations=5000,
    )
    assert result == {"id": "run1", "status": "queued"}


@pytest.mark.asyncio
async def test_generate_executive_report_pdf_vs_powerpoint_routing(monkeypatch):
    seen_paths = []

    def handler(request):
        seen_paths.append(request.url.path)
        return httpx.Response(202, json={"id": "r1", "status": "queued"})

    _install_transport(monkeypatch, handler)
    client = RiskPlatformClient(Settings(api_base_url="http://apps-api.test"), token="tok")
    await client.generate_executive_report("pdf")
    await client.generate_executive_report("powerpoint", template="two_slide_elt")
    assert seen_paths == ["/api/v1/reports/pdf", "/api/v1/reports/powerpoint"]


@pytest.mark.asyncio
async def test_error_response_raises_with_parsed_detail(monkeypatch):
    def handler(request):
        return httpx.Response(403, json={"detail": "missing required permission: view_report_runs"})

    _install_transport(monkeypatch, handler)
    client = RiskPlatformClient(Settings(api_base_url="http://apps-api.test"), token="tok")
    with pytest.raises(RiskPlatformAPIError) as exc_info:
        await client.get_report_run("run1")
    assert exc_info.value.status_code == 403
    assert "missing required permission" in exc_info.value.detail


@pytest.mark.asyncio
async def test_error_response_falls_back_to_raw_text_when_not_json(monkeypatch):
    def handler(request):
        return httpx.Response(500, text="internal server error")

    _install_transport(monkeypatch, handler)
    client = RiskPlatformClient(Settings(api_base_url="http://apps-api.test"), token="tok")
    with pytest.raises(RiskPlatformAPIError) as exc_info:
        await client.get_risk("abc")
    assert exc_info.value.status_code == 500
    assert "internal server error" in exc_info.value.detail


@pytest.mark.asyncio
async def test_no_content_response_returns_empty_dict(monkeypatch):
    def handler(request):
        return httpx.Response(204)

    _install_transport(monkeypatch, handler)
    client = RiskPlatformClient(Settings(api_base_url="http://apps-api.test"), token="tok")
    assert await client.get_risk("abc") == {}
