from apps.api.tests.conftest import login


def create_risk(client, headers, title="Snapshot API risk"):
    payload = {
        "title": title,
        "assessment": {
            "likelihood": 3,
            "impact_scores": {
                "financial": 3, "customer_service": 3, "operational_delivery": 3,
                "legal_regulatory": 3, "reputation": 3, "health_safety": 3,
            },
            "control_effectiveness": 3,
        },
    }
    response = client.post("/api/v1/risks", json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()


class TestSnapshotsApi:
    def test_risk_manager_can_capture_snapshot(self, client):
        headers = login(client, "risk.manager@example.com")
        create_risk(client, headers)
        response = client.post("/api/v1/snapshots", json={"label": "Month end"}, headers=headers)
        assert response.status_code == 201, response.text
        assert response.json()["risk_count"] == 1

    def test_non_manager_roles_forbidden(self, client):
        for email in ["viewer@example.com", "risk.owner@example.com", "control.owner@example.com",
                      "executive@example.com", "auditor@example.com"]:
            headers = login(client, email)
            response = client.post("/api/v1/snapshots", json={"label": "x"}, headers=headers)
            assert response.status_code == 403, f"{email} should not manage snapshots"

    def test_list_snapshots(self, client):
        headers = login(client, "risk.manager@example.com")
        client.post("/api/v1/snapshots", json={"label": "First"}, headers=headers)
        client.post("/api/v1/snapshots", json={"label": "Second"}, headers=headers)
        response = client.get("/api/v1/snapshots", headers=headers)
        assert len(response.json()) == 2


class TestWhatChanged:
    def test_new_risk_shows_up(self, client):
        headers = login(client, "risk.manager@example.com")
        snapshot = client.post("/api/v1/snapshots", json={"label": "Baseline"}, headers=headers).json()
        create_risk(client, headers, title="Created after baseline")

        response = client.get(
            "/api/v1/dashboard/what-changed", params={"since_snapshot": snapshot["id"]}, headers=headers
        )
        assert response.status_code == 200
        titles = [r["title"] for r in response.json()["new_risks"]]
        assert "Created after baseline" in titles

    def test_unknown_snapshot_is_404(self, client):
        headers = login(client, "risk.manager@example.com")
        response = client.get(
            "/api/v1/dashboard/what-changed",
            params={"since_snapshot": "00000000-0000-0000-0000-000000000000"},
            headers=headers,
        )
        assert response.status_code == 404

    def test_requires_authentication(self, client):
        response = client.get(
            "/api/v1/dashboard/what-changed",
            params={"since_snapshot": "00000000-0000-0000-0000-000000000000"},
        )
        assert response.status_code == 401


class TestTrends:
    def test_trend_has_a_current_point(self, client):
        headers = login(client, "viewer@example.com")
        response = client.get("/api/v1/dashboard/trends", headers=headers)
        assert response.status_code == 200
        assert response.json()[-1]["label"] == "Current"

    def test_trend_reflects_captured_snapshot(self, client):
        manager_headers = login(client, "risk.manager@example.com")
        create_risk(client, manager_headers)
        client.post("/api/v1/snapshots", json={"label": "Captured period"}, headers=manager_headers)

        viewer_headers = login(client, "viewer@example.com")
        response = client.get("/api/v1/dashboard/trends", headers=viewer_headers)
        labels = [p["label"] for p in response.json()]
        assert "Captured period" in labels
