"""Tests that auth_mode actually changes what's reachable, not just what
get_current_user does internally. Each test builds its own fresh app via
create_app() (rather than importing the shared `apps.api.app.main.app`
singleton, which was already built in mock mode at import time) so that
route registration itself — not just request handling — is under test.
"""

from fastapi.testclient import TestClient

from apps.api.app.deps import get_object_store
from apps.api.app.main import create_app
from apps.api.tests.conftest import login
from packages.shared.storage import LocalFileSystemStore


def _fresh_client(monkeypatch, tmp_path, auth_mode: str, iap_audience: str | None = None):
    monkeypatch.setenv("AUTH_MODE", auth_mode)
    if iap_audience is not None:
        monkeypatch.setenv("IAP_AUDIENCE", iap_audience)
    else:
        monkeypatch.delenv("IAP_AUDIENCE", raising=False)
    app = create_app()
    app.dependency_overrides[get_object_store] = lambda: LocalFileSystemStore(tmp_path / "storage")
    return TestClient(app)


class TestMockModeRouteRegistration:
    def test_mock_login_is_registered_by_default(self, monkeypatch, tmp_path, seeded):
        client = _fresh_client(monkeypatch, tmp_path, "mock")
        assert client.post("/api/v1/auth/mock-login", json={"email": "viewer@example.com"}).status_code == 200


class TestIapModeRouteRegistration:
    def test_mock_login_is_not_registered_at_all(self, monkeypatch, tmp_path, seeded):
        client = _fresh_client(monkeypatch, tmp_path, "iap", iap_audience="test-audience")
        response = client.post("/api/v1/auth/mock-login", json={"email": "viewer@example.com"})
        assert response.status_code == 404

    def test_me_still_works_via_the_iap_header(self, monkeypatch, tmp_path, seeded):
        monkeypatch.setattr(
            "apps.api.app.deps.verify_iap_assertion",
            lambda assertion, audience: "risk.manager@example.com",
        )
        client = _fresh_client(monkeypatch, tmp_path, "iap", iap_audience="test-audience")
        response = client.get(
            "/api/v1/auth/me", headers={"X-Goog-IAP-JWT-Assertion": "whatever-google-signed"}
        )
        assert response.status_code == 200, response.text
        assert response.json()["email"] == "risk.manager@example.com"

    def test_missing_iap_header_is_rejected(self, monkeypatch, tmp_path, seeded):
        client = _fresh_client(monkeypatch, tmp_path, "iap", iap_audience="test-audience")
        assert client.get("/api/v1/auth/me").status_code == 401

    def test_unknown_email_in_a_verified_assertion_is_still_rejected(
        self, monkeypatch, tmp_path, seeded
    ):
        monkeypatch.setattr(
            "apps.api.app.deps.verify_iap_assertion",
            lambda assertion, audience: "not-a-seeded-user@example.com",
        )
        client = _fresh_client(monkeypatch, tmp_path, "iap", iap_audience="test-audience")
        response = client.get(
            "/api/v1/auth/me", headers={"X-Goog-IAP-JWT-Assertion": "whatever-google-signed"}
        )
        assert response.status_code == 401

    def test_me_also_works_via_a_forwarded_authorization_bearer_token(
        self, monkeypatch, tmp_path, seeded
    ):
        """The MCP gateway never goes through IAP at all — it forwards
        whatever Google-signed ID token its caller presented as a plain
        Authorization header (see deps.py's _get_current_user_iap
        docstring). Must work identically to the IAP-injected header."""
        monkeypatch.setattr(
            "apps.api.app.deps.verify_iap_assertion",
            lambda assertion, audience: "risk.manager@example.com",
        )
        client = _fresh_client(monkeypatch, tmp_path, "iap", iap_audience="test-audience")
        response = client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer some-google-id-token"}
        )
        assert response.status_code == 200, response.text
        assert response.json()["email"] == "risk.manager@example.com"

    def test_missing_iap_audience_config_fails_closed_not_open(self, monkeypatch, tmp_path, seeded):
        client = _fresh_client(monkeypatch, tmp_path, "iap", iap_audience=None)
        response = client.get(
            "/api/v1/auth/me", headers={"X-Goog-IAP-JWT-Assertion": "whatever"}
        )
        assert response.status_code == 500

    def test_a_mock_style_bearer_token_fails_real_verification_in_iap_mode(
        self, monkeypatch, tmp_path, seeded
    ):
        """Proves the mock scheme genuinely stops working once auth_mode
        flips: a raw-UUID mock token IS read from the Authorization header
        (iap mode does accept that header — see the next test — for real
        Google ID tokens forwarded by the MCP gateway), but it is not a
        valid Google-signed JWT, so real verification rejects it. Uses the
        real, unmocked verify_iap_assertion deliberately."""
        mock_client = _fresh_client(monkeypatch, tmp_path, "mock")
        headers = login(mock_client, "risk.manager@example.com")

        iap_client = _fresh_client(monkeypatch, tmp_path, "iap", iap_audience="test-audience")
        response = iap_client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401
