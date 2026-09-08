"""Thin, permissioned client of apps/api (ADR 0009). Every method here maps
to exactly one existing REST call, forwarding the caller's own bearer token
— never a shared or more-privileged gateway credential. This module has no
database import, no ORM, no filesystem access: if apps/api rejects a call
(401/403/404/422), that rejection is surfaced as-is, never worked around.

Two identities travel on each call, in two different headers, because in
production they answer two different questions:

  - `Authorization`: "is this gateway itself allowed to reach apps/api at
    all" — apps/api's Cloud Run ingress requires IAM authentication in
    production (Milestone 11), so this must carry the gateway's OWN
    service-account identity token, minted fresh per call via the Cloud
    Run metadata server (google-auth's fetch_id_token). Off Cloud Run —
    local dev, this session's own docker-compose stack — there is no
    metadata server, fetch_id_token simply fails, and this header falls
    back to the caller's own token instead: harmless, because apps/api's
    mock auth mode (the only mode reachable without Cloud Run) reads
    exactly that header anyway.
  - `X-Goog-IAP-JWT-Assertion`: "who is the human". Always carries the
    caller's own token as-is. apps/api's iap-mode identity check reads
    this header first (see apps/api/app/deps.py); its mock mode ignores
    it entirely, so setting it in local dev is a no-op, not a conflict.
"""

from __future__ import annotations

import httpx

try:
    from google.auth.exceptions import GoogleAuthError
    from google.auth.transport.requests import Request as GoogleAuthRequest
    from google.oauth2.id_token import fetch_id_token
except ImportError:  # pragma: no cover - google-auth is a required dependency; defensive only
    GoogleAuthError = Exception
    GoogleAuthRequest = None
    fetch_id_token = None

from apps.mcp.app.config import Settings


class RiskPlatformAPIError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"apps/api returned {status_code}: {detail}")


def service_identity_token(audience: str) -> str | None:
    """Only ever succeeds when actually running on GCP infrastructure with
    a metadata server present (Cloud Run, GCE, GKE) — returns None
    everywhere else (local dev, CI, this session's own container) rather
    than raising, since the caller falls back to the human's own token in
    that case."""
    if GoogleAuthRequest is None:
        return None
    try:
        return fetch_id_token(GoogleAuthRequest(), audience)
    except (GoogleAuthError, OSError, ValueError):
        return None


class RiskPlatformClient:
    def __init__(self, settings: Settings, token: str):
        self._base_url = settings.api_base_url
        self._timeout = settings.request_timeout_seconds
        service_token = service_identity_token(audience=self._base_url)
        self._headers = {
            "Authorization": f"Bearer {service_token or token}",
            "X-Goog-IAP-JWT-Assertion": token,
        }

    async def _request(self, method: str, path: str, **kwargs) -> dict | list:
        async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as client:
            response = await client.request(method, path, headers=self._headers, **kwargs)
        if response.status_code >= 400:
            detail = response.text
            try:
                detail = response.json().get("detail", detail)
            except ValueError:
                pass
            raise RiskPlatformAPIError(response.status_code, str(detail))
        if response.status_code == 204:
            return {}
        return response.json()

    async def get_risk(self, risk_id: str) -> dict:
        return await self._request("GET", f"/api/v1/risks/{risk_id}")

    async def search_risks(
        self,
        query: str | None = None,
        status: str | None = None,
        category_id: str | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> list:
        params = {"page": page, "page_size": page_size}
        if query:
            params["q"] = query
        if status:
            params["status"] = status
        if category_id:
            params["category_id"] = category_id
        return await self._request("GET", "/api/v1/risks", params=params)

    async def get_executive_dashboard(self) -> dict:
        return await self._request("GET", "/api/v1/dashboard/executive")

    async def get_governance_health(self) -> dict:
        return await self._request("GET", "/api/v1/dashboard/governance")

    async def run_monte_carlo(
        self,
        risk_id: str,
        distribution_type: str,
        loss_min: float,
        loss_most_likely: float,
        loss_max: float,
        annual_event_frequency: float = 1.0,
        iterations: int = 10_000,
        seed: int = 42,
    ) -> dict:
        return await self._request(
            "POST",
            "/api/v1/simulations",
            json={
                "risk_id": risk_id,
                "distribution_type": distribution_type,
                "loss_min": loss_min,
                "loss_most_likely": loss_most_likely,
                "loss_max": loss_max,
                "annual_event_frequency": annual_event_frequency,
                "iterations": iterations,
                "seed": seed,
            },
        )

    async def get_simulation_run(self, run_id: str) -> dict:
        return await self._request("GET", f"/api/v1/simulations/{run_id}")

    async def generate_executive_report(
        self, report_format: str, template: str = "one_slide"
    ) -> dict:
        path = "/api/v1/reports/pdf" if report_format == "pdf" else "/api/v1/reports/powerpoint"
        payload: dict = {}
        if report_format == "powerpoint":
            payload["template"] = template
        return await self._request("POST", path, json=payload)

    async def get_report_run(self, run_id: str) -> dict:
        return await self._request("GET", f"/api/v1/reports/runs/{run_id}")
