from apps.api.tests.conftest import login


def create_risk(client, headers, title="Scenario-linked risk"):
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
    assert response.status_code == 201, response.text
    return response.json()


class TestScenarioCrud:
    def test_risk_manager_can_create_scenario(self, client):
        headers = login(client, "risk.manager@example.com")
        response = client.post(
            "/api/v1/scenarios",
            json={"name": "Major cyber incident", "description": "Ransomware across two regions"},
            headers=headers,
        )
        assert response.status_code == 201, response.text
        assert response.json()["linked_risk_ids"] == []

    def test_risk_owner_cannot_create_scenario(self, client):
        headers = login(client, "risk.owner@example.com")
        response = client.post("/api/v1/scenarios", json={"name": "x"}, headers=headers)
        assert response.status_code == 403

    def test_viewer_can_list_and_read_scenarios(self, client):
        manager_headers = login(client, "risk.manager@example.com")
        client.post("/api/v1/scenarios", json={"name": "Supply chain disruption"}, headers=manager_headers)

        viewer_headers = login(client, "viewer@example.com")
        list_response = client.get("/api/v1/scenarios", headers=viewer_headers)
        assert list_response.status_code == 200
        assert len(list_response.json()) == 1

    def test_update_scenario(self, client):
        headers = login(client, "admin@example.com")
        scenario = client.post("/api/v1/scenarios", json={"name": "Draft scenario"}, headers=headers).json()
        response = client.patch(
            f"/api/v1/scenarios/{scenario['id']}",
            json={"description": "Now with a description"},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["description"] == "Now with a description"

    def test_risk_owner_cannot_update_scenario(self, client):
        manager_headers = login(client, "risk.manager@example.com")
        scenario = client.post("/api/v1/scenarios", json={"name": "x"}, headers=manager_headers).json()

        owner_headers = login(client, "risk.owner@example.com")
        response = client.patch(
            f"/api/v1/scenarios/{scenario['id']}", json={"name": "y"}, headers=owner_headers
        )
        assert response.status_code == 403

    def test_unknown_scenario_is_404(self, client):
        headers = login(client, "risk.manager@example.com")
        response = client.get(
            "/api/v1/scenarios/00000000-0000-0000-0000-000000000000", headers=headers
        )
        assert response.status_code == 404


class TestScenarioRiskLinking:
    def test_link_and_unlink_risk(self, client):
        headers = login(client, "risk.manager@example.com")
        risk = create_risk(client, headers)
        scenario = client.post("/api/v1/scenarios", json={"name": "Linked scenario"}, headers=headers).json()

        link_response = client.post(
            f"/api/v1/scenarios/{scenario['id']}/risks", params={"risk_id": risk["id"]}, headers=headers
        )
        assert link_response.status_code == 201
        assert risk["id"] in link_response.json()["linked_risk_ids"]

        unlink_response = client.delete(
            f"/api/v1/scenarios/{scenario['id']}/risks/{risk['id']}", headers=headers
        )
        assert unlink_response.status_code == 204

        get_response = client.get(f"/api/v1/scenarios/{scenario['id']}", headers=headers)
        assert risk["id"] not in get_response.json()["linked_risk_ids"]

    def test_linking_is_idempotent(self, client):
        headers = login(client, "risk.manager@example.com")
        risk = create_risk(client, headers)
        scenario = client.post("/api/v1/scenarios", json={"name": "x"}, headers=headers).json()

        client.post(f"/api/v1/scenarios/{scenario['id']}/risks", params={"risk_id": risk["id"]}, headers=headers)
        client.post(f"/api/v1/scenarios/{scenario['id']}/risks", params={"risk_id": risk["id"]}, headers=headers)

        get_response = client.get(f"/api/v1/scenarios/{scenario['id']}", headers=headers)
        assert get_response.json()["linked_risk_ids"].count(risk["id"]) == 1

    def test_risk_owner_cannot_link_risk(self, client):
        manager_headers = login(client, "risk.manager@example.com")
        risk = create_risk(client, manager_headers)
        scenario = client.post("/api/v1/scenarios", json={"name": "x"}, headers=manager_headers).json()

        owner_headers = login(client, "risk.owner@example.com")
        response = client.post(
            f"/api/v1/scenarios/{scenario['id']}/risks", params={"risk_id": risk["id"]}, headers=owner_headers
        )
        assert response.status_code == 403


class TestScenarioExposure:
    def test_reports_risks_missing_simulation_config(self, client):
        headers = login(client, "risk.manager@example.com")
        risk = create_risk(client, headers)
        scenario = client.post("/api/v1/scenarios", json={"name": "x"}, headers=headers).json()
        client.post(f"/api/v1/scenarios/{scenario['id']}/risks", params={"risk_id": risk["id"]}, headers=headers)

        response = client.get(f"/api/v1/scenarios/{scenario['id']}/exposure", headers=headers)
        body = response.json()
        assert body["linked_risk_count"] == 1
        assert risk["id"] in body["risks_missing_simulation_config"]
        assert body["latest_run_id"] is None

    def test_configured_risk_is_not_reported_missing(self, client):
        headers = login(client, "risk.manager@example.com")
        risk = create_risk(client, headers)
        client.post(
            "/api/v1/simulations",
            json={
                "risk_id": risk["id"], "distribution_type": "pert", "loss_min": 1000,
                "loss_most_likely": 5000, "loss_max": 20000, "iterations": 200, "seed": 1,
            },
            headers=headers,
        )
        scenario = client.post("/api/v1/scenarios", json={"name": "x"}, headers=headers).json()
        client.post(f"/api/v1/scenarios/{scenario['id']}/risks", params={"risk_id": risk["id"]}, headers=headers)

        response = client.get(f"/api/v1/scenarios/{scenario['id']}/exposure", headers=headers)
        assert response.json()["risks_missing_simulation_config"] == []
