from apps.api.tests.conftest import login


def create_risk(client, headers, title="Issue/incident risk"):
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


class TestIssues:
    def test_risk_owner_can_create_issue(self, client):
        headers = login(client, "risk.owner@example.com")
        risk = create_risk(client, headers)
        response = client.post(
            "/api/v1/issues",
            json={"risk_id": risk["id"], "description": "Control gap found", "source": "audit"},
            headers=headers,
        )
        assert response.status_code == 201, response.text
        assert response.json()["issue_code"].startswith("ISS-")
        assert response.json()["status"] == "open"

    def test_viewer_cannot_create_issue(self, client):
        headers = login(client, "viewer@example.com")
        response = client.post("/api/v1/issues", json={"description": "x"}, headers=headers)
        assert response.status_code == 403

    def test_update_issue_status(self, client):
        headers = login(client, "risk.owner@example.com")
        issue = client.post("/api/v1/issues", json={"description": "x"}, headers=headers).json()
        response = client.patch(
            f"/api/v1/issues/{issue['id']}", json={"status": "resolved"}, headers=headers
        )
        assert response.status_code == 200
        assert response.json()["status"] == "resolved"

    def test_risk_scoped_issue_list(self, client):
        headers = login(client, "risk.owner@example.com")
        risk = create_risk(client, headers)
        client.post("/api/v1/issues", json={"risk_id": risk["id"], "description": "linked"}, headers=headers)
        client.post("/api/v1/issues", json={"description": "unlinked"}, headers=headers)

        response = client.get(f"/api/v1/risks/{risk['id']}/issues", headers=headers)
        descriptions = [i["description"] for i in response.json()]
        assert descriptions == ["linked"]


class TestIncidents:
    def test_control_owner_can_create_incident(self, client):
        headers = login(client, "control.owner@example.com")
        response = client.post(
            "/api/v1/incidents",
            json={
                "description": "Control failed to detect intrusion",
                "incident_date": "2026-02-01",
                "severity": "high",
                "suggests_likelihood_increase": True,
            },
            headers=headers,
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["incident_code"].startswith("INC-")
        assert body["review_triggered_at"] is None

    def test_viewer_cannot_create_incident(self, client):
        headers = login(client, "viewer@example.com")
        response = client.post(
            "/api/v1/incidents",
            json={"description": "x", "incident_date": "2026-01-01", "severity": "low"},
            headers=headers,
        )
        assert response.status_code == 403

    def test_trigger_review_sets_risk_next_review_date(self, client):
        owner_headers = login(client, "risk.owner@example.com")
        risk = create_risk(client, owner_headers)

        incident = client.post(
            "/api/v1/incidents",
            json={
                "risk_id": risk["id"], "description": "Outage", "incident_date": "2026-02-01",
                "severity": "critical",
            },
            headers=owner_headers,
        ).json()

        manager_headers = login(client, "risk.manager@example.com")
        response = client.post(
            f"/api/v1/incidents/{incident['id']}/trigger-review", headers=manager_headers
        )
        assert response.status_code == 200
        assert response.json()["review_triggered_at"] is not None

        updated_risk = client.get(f"/api/v1/risks/{risk['id']}", headers=manager_headers).json()
        assert updated_risk["next_review_date"] is not None

    def test_risk_owner_cannot_trigger_review(self, client):
        owner_headers = login(client, "risk.owner@example.com")
        risk = create_risk(client, owner_headers)
        incident = client.post(
            "/api/v1/incidents",
            json={
                "risk_id": risk["id"], "description": "Outage", "incident_date": "2026-02-01",
                "severity": "low",
            },
            headers=owner_headers,
        ).json()

        response = client.post(
            f"/api/v1/incidents/{incident['id']}/trigger-review", headers=owner_headers
        )
        assert response.status_code == 403

    def test_trigger_review_without_linked_risk_is_400(self, client):
        headers = login(client, "risk.manager@example.com")
        incident = client.post(
            "/api/v1/incidents",
            json={"description": "Unlinked incident", "incident_date": "2026-01-01", "severity": "low"},
            headers=headers,
        ).json()

        response = client.post(f"/api/v1/incidents/{incident['id']}/trigger-review", headers=headers)
        assert response.status_code == 400

    def test_risk_scoped_incident_list(self, client):
        headers = login(client, "risk.owner@example.com")
        risk = create_risk(client, headers)
        client.post(
            "/api/v1/incidents",
            json={"risk_id": risk["id"], "description": "linked", "incident_date": "2026-01-01", "severity": "low"},
            headers=headers,
        )
        response = client.get(f"/api/v1/risks/{risk['id']}/incidents", headers=headers)
        assert len(response.json()) == 1
