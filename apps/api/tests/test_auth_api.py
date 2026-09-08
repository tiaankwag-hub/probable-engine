"""Auth endpoint tests: mock-login (existing) plus GET /auth/me, which the
Milestone 10 MCP gateway relies on to resolve a forwarded bearer token to an
identity and role list without any auth mechanism of its own.
"""

from apps.api.tests.conftest import login


class TestWhoAmI:
    def test_returns_identity_and_roles_for_a_valid_token(self, client):
        headers = login(client, "risk.manager@example.com")
        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["email"] == "risk.manager@example.com"
        assert "risk_manager" in body["roles"]
        assert body["user_id"]

    def test_rejects_missing_token(self, client):
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401

    def test_rejects_garbage_token(self, client):
        response = client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-uuid"}
        )
        assert response.status_code == 401

    def test_rejects_unknown_but_valid_uuid(self, client):
        import uuid

        response = client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {uuid.uuid4()}"}
        )
        assert response.status_code == 401
