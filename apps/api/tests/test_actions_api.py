from datetime import date, timedelta

from apps.api.tests.conftest import login


def create_risk(client, headers, title="Risk with an action"):
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


class TestActionCreate:
    def test_risk_owner_can_create_action(self, client):
        headers = login(client, "risk.owner@example.com")
        risk = create_risk(client, headers)
        response = client.post(
            "/api/v1/actions",
            json={"risk_id": risk["id"], "title": "Onboard secondary vendor", "priority": "high"},
            headers=headers,
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["action_code"].startswith("ACT-")
        assert body["status"] == "open"
        assert body["completion_percent"] == 0

    def test_viewer_cannot_create_action(self, client):
        headers = login(client, "viewer@example.com")
        response = client.post("/api/v1/actions", json={"title": "Do something"}, headers=headers)
        assert response.status_code == 403

    def test_control_owner_can_create_action(self, client):
        headers = login(client, "control.owner@example.com")
        response = client.post(
            "/api/v1/actions", json={"title": "Automate control X"}, headers=headers
        )
        assert response.status_code == 201


class TestActionUpdate:
    def test_owner_can_update_own_action(self, client):
        headers = login(client, "risk.owner@example.com")
        action = client.post(
            "/api/v1/actions", json={"title": "My action"}, headers=headers
        ).json()
        response = client.patch(
            f"/api/v1/actions/{action['id']}",
            json={"completion_percent": 50, "status": "in_progress"},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["completion_percent"] == 50

    def test_non_owner_cannot_update_others_action(self, client):
        owner_headers = login(client, "risk.owner@example.com")
        action = client.post(
            "/api/v1/actions", json={"title": "My action"}, headers=owner_headers
        ).json()

        other_headers = login(client, "control.owner@example.com")
        response = client.patch(
            f"/api/v1/actions/{action['id']}", json={"completion_percent": 90}, headers=other_headers
        )
        assert response.status_code == 403

    def test_risk_manager_can_update_any_action(self, client):
        owner_headers = login(client, "risk.owner@example.com")
        action = client.post(
            "/api/v1/actions", json={"title": "My action"}, headers=owner_headers
        ).json()

        manager_headers = login(client, "risk.manager@example.com")
        response = client.patch(
            f"/api/v1/actions/{action['id']}", json={"status": "cancelled"}, headers=manager_headers
        )
        assert response.status_code == 200

    def test_completing_action_sets_completed_date_and_full_completion(self, client):
        headers = login(client, "risk.owner@example.com")
        action = client.post(
            "/api/v1/actions", json={"title": "My action"}, headers=headers
        ).json()
        response = client.patch(
            f"/api/v1/actions/{action['id']}", json={"status": "completed"}, headers=headers
        )
        body = response.json()
        assert body["completion_percent"] == 100
        assert body["completed_date"] is not None


class TestActionListing:
    def test_overdue_filter_returns_only_past_due_open_actions(self, client):
        headers = login(client, "risk.owner@example.com")
        overdue_due = (date.today() - timedelta(days=5)).isoformat()
        future_due = (date.today() + timedelta(days=5)).isoformat()

        client.post(
            "/api/v1/actions",
            json={"title": "Overdue action", "due_date": overdue_due},
            headers=headers,
        )
        client.post(
            "/api/v1/actions",
            json={"title": "Future action", "due_date": future_due},
            headers=headers,
        )

        response = client.get("/api/v1/actions", params={"overdue": True}, headers=headers)
        titles = [a["title"] for a in response.json()]
        assert "Overdue action" in titles
        assert "Future action" not in titles

    def test_completed_overdue_action_excluded_from_overdue_filter(self, client):
        headers = login(client, "risk.owner@example.com")
        overdue_due = (date.today() - timedelta(days=5)).isoformat()
        action = client.post(
            "/api/v1/actions",
            json={"title": "Completed overdue action", "due_date": overdue_due},
            headers=headers,
        ).json()
        client.patch(f"/api/v1/actions/{action['id']}", json={"status": "completed"}, headers=headers)

        response = client.get("/api/v1/actions", params={"overdue": True}, headers=headers)
        titles = [a["title"] for a in response.json()]
        assert "Completed overdue action" not in titles

    def test_get_risk_actions_scoped_to_risk(self, client):
        headers = login(client, "risk.owner@example.com")
        risk1 = create_risk(client, headers, title="Risk 1")
        risk2 = create_risk(client, headers, title="Risk 2")
        client.post("/api/v1/actions", json={"risk_id": risk1["id"], "title": "For risk 1"}, headers=headers)
        client.post("/api/v1/actions", json={"risk_id": risk2["id"], "title": "For risk 2"}, headers=headers)

        response = client.get(f"/api/v1/risks/{risk1['id']}/actions", headers=headers)
        titles = [a["title"] for a in response.json()]
        assert titles == ["For risk 1"]
