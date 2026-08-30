import pytest

from apps.api.tests.conftest import login

VALID_PAYLOAD = {
    "category_id": None,
    "business_unit": None,
    "appetite_band": "low",
    "tolerance_band": "moderate",
    "limit_value": 15.0,
    "effective_from": "2026-01-01",
    "effective_to": None,
}

NON_ADMIN_EMAILS = [
    "viewer@example.com",
    "risk.owner@example.com",
    "control.owner@example.com",
    "risk.manager@example.com",
    "executive@example.com",
    "auditor@example.com",
]


class TestAppetiteCreate:
    def test_administrator_can_create_appetite_config(self, client):
        headers = login(client, "admin@example.com")
        response = client.post("/api/v1/risk-appetite", json=VALID_PAYLOAD, headers=headers)
        assert response.status_code == 201, response.text
        assert response.json()["appetite_band"] == "low"

    @pytest.mark.parametrize("email", NON_ADMIN_EMAILS)
    def test_non_administrator_roles_forbidden(self, client, email):
        headers = login(client, email)
        response = client.post("/api/v1/risk-appetite", json=VALID_PAYLOAD, headers=headers)
        assert response.status_code == 403

    def test_tolerance_below_appetite_rejected(self, client):
        headers = login(client, "admin@example.com")
        bad = dict(VALID_PAYLOAD, appetite_band="high", tolerance_band="low")
        response = client.post("/api/v1/risk-appetite", json=bad, headers=headers)
        assert response.status_code == 422

    def test_invalid_band_name_rejected(self, client):
        headers = login(client, "admin@example.com")
        bad = dict(VALID_PAYLOAD, appetite_band="critical")
        response = client.post("/api/v1/risk-appetite", json=bad, headers=headers)
        assert response.status_code == 422

    def test_effective_to_before_effective_from_rejected(self, client):
        headers = login(client, "admin@example.com")
        bad = dict(VALID_PAYLOAD, effective_from="2026-06-01", effective_to="2026-01-01")
        response = client.post("/api/v1/risk-appetite", json=bad, headers=headers)
        assert response.status_code == 422


class TestAppetiteList:
    def test_any_role_can_list(self, client):
        admin_headers = login(client, "admin@example.com")
        client.post("/api/v1/risk-appetite", json=VALID_PAYLOAD, headers=admin_headers)

        viewer_headers = login(client, "viewer@example.com")
        response = client.get("/api/v1/risk-appetite", headers=viewer_headers)
        assert response.status_code == 200
        assert len(response.json()) == 1


class TestAppetiteUpdate:
    def test_administrator_can_update(self, client):
        headers = login(client, "admin@example.com")
        created = client.post("/api/v1/risk-appetite", json=VALID_PAYLOAD, headers=headers).json()
        updated_payload = dict(VALID_PAYLOAD, appetite_band="moderate")
        response = client.patch(
            f"/api/v1/risk-appetite/{created['id']}", json=updated_payload, headers=headers
        )
        assert response.status_code == 200
        assert response.json()["appetite_band"] == "moderate"
