from apps.api.tests.conftest import login
from apps.worker.app.main import process_one


def create_risk(client, headers, title="Simulated risk"):
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


def config_payload(risk_id, **overrides):
    payload = {
        "risk_id": risk_id,
        "distribution_type": "triangular",
        "loss_min": 1000,
        "loss_most_likely": 10000,
        "loss_max": 100000,
        "annual_event_frequency": 2.0,
        "iterations": 500,
        "seed": 1,
    }
    payload.update(overrides)
    return payload


class TestCreateConfigAndRun:
    def test_risk_owner_can_run_simulation_for_own_risk(self, client):
        headers = login(client, "risk.owner@example.com")
        risk = create_risk(client, headers)
        response = client.post("/api/v1/simulations", json=config_payload(risk["id"]), headers=headers)
        assert response.status_code == 202, response.text
        assert response.json()["status"] == "pending"

    def test_risk_owner_cannot_run_simulation_for_someone_elses_risk(self, client):
        owner_headers = login(client, "risk.owner@example.com")
        risk = create_risk(client, owner_headers)

        other_owner_headers = login(client, "control.owner@example.com")
        response = client.post(
            "/api/v1/simulations", json=config_payload(risk["id"]), headers=other_owner_headers
        )
        assert response.status_code == 403

    def test_control_owner_cannot_run_simulation(self, client):
        headers = login(client, "control.owner@example.com")
        risk = create_risk(client, login(client, "risk.owner@example.com"))
        response = client.post("/api/v1/simulations", json=config_payload(risk["id"]), headers=headers)
        assert response.status_code == 403

    def test_risk_manager_can_run_simulation_for_any_risk(self, client):
        owner_headers = login(client, "risk.owner@example.com")
        risk = create_risk(client, owner_headers)

        manager_headers = login(client, "risk.manager@example.com")
        response = client.post(
            "/api/v1/simulations", json=config_payload(risk["id"]), headers=manager_headers
        )
        assert response.status_code == 202

    def test_executive_cannot_run_simulation(self, client):
        headers = login(client, "executive@example.com")
        risk = create_risk(client, login(client, "risk.owner@example.com"))
        response = client.post("/api/v1/simulations", json=config_payload(risk["id"]), headers=headers)
        assert response.status_code == 403

    def test_unknown_risk_is_404(self, client):
        headers = login(client, "risk.manager@example.com")
        response = client.post(
            "/api/v1/simulations",
            json=config_payload("00000000-0000-0000-0000-000000000000"),
            headers=headers,
        )
        assert response.status_code == 404


class TestSimulationRunLifecycle:
    def test_run_transitions_to_succeeded_after_processing(self, client):
        headers = login(client, "risk.manager@example.com")
        risk = create_risk(client, headers)
        run = client.post("/api/v1/simulations", json=config_payload(risk["id"]), headers=headers).json()

        assert process_one() is True

        response = client.get(f"/api/v1/simulations/{run['id']}", headers=headers)
        body = response.json()
        assert body["status"] == "succeeded"
        assert body["result"]["expected_annual_loss"] >= 0
        assert body["result"]["p99"] >= body["result"]["p95"] >= body["result"]["p90"]
        assert len(body["result"]["histogram"]) > 0
        assert body["config"]["distribution_type"] == "triangular"

    def test_reproducible_given_same_seed(self, client):
        headers = login(client, "risk.manager@example.com")
        risk = create_risk(client, headers)

        run_a = client.post(
            "/api/v1/simulations", json=config_payload(risk["id"], seed=99), headers=headers
        ).json()
        process_one()
        run_b = client.post(
            "/api/v1/simulations", json=config_payload(risk["id"], seed=99), headers=headers
        ).json()
        process_one()

        result_a = client.get(f"/api/v1/simulations/{run_a['id']}", headers=headers).json()["result"]
        result_b = client.get(f"/api/v1/simulations/{run_b['id']}", headers=headers).json()["result"]
        assert result_a["expected_annual_loss"] == result_b["expected_annual_loss"]

    def test_get_run_requires_view_permission(self, client):
        headers = login(client, "risk.manager@example.com")
        risk = create_risk(client, headers)
        run = client.post("/api/v1/simulations", json=config_payload(risk["id"]), headers=headers).json()

        control_owner_headers = login(client, "control.owner@example.com")
        response = client.get(f"/api/v1/simulations/{run['id']}", headers=control_owner_headers)
        assert response.status_code == 403

    def test_unknown_run_is_404(self, client):
        headers = login(client, "risk.manager@example.com")
        response = client.get(
            "/api/v1/simulations/00000000-0000-0000-0000-000000000000", headers=headers
        )
        assert response.status_code == 404


class TestListRuns:
    def test_history_filtered_by_risk(self, client):
        headers = login(client, "risk.manager@example.com")
        risk_a = create_risk(client, headers, title="Risk A")
        risk_b = create_risk(client, headers, title="Risk B")
        client.post("/api/v1/simulations", json=config_payload(risk_a["id"]), headers=headers)
        client.post("/api/v1/simulations", json=config_payload(risk_b["id"]), headers=headers)

        response = client.get("/api/v1/simulations", params={"risk_id": risk_a["id"]}, headers=headers)
        assert response.status_code == 200
        assert len(response.json()) == 1


class TestPortfolioSimulation:
    def test_portfolio_requires_run_any_permission(self, client):
        headers = login(client, "risk.owner@example.com")
        scenario = client.post(
            "/api/v1/scenarios", json={"name": "Regional outage"}, headers=login(client, "risk.manager@example.com")
        ).json()
        response = client.post(
            "/api/v1/simulations/portfolio",
            json={"scenario_id": scenario["id"], "iterations": 200, "seed": 1},
            headers=headers,
        )
        assert response.status_code == 403

    def test_portfolio_run_succeeds_with_configured_risks(self, client):
        manager_headers = login(client, "risk.manager@example.com")
        risk_a = create_risk(client, manager_headers, title="Risk A")
        risk_b = create_risk(client, manager_headers, title="Risk B")

        client.post("/api/v1/simulations", json=config_payload(risk_a["id"]), headers=manager_headers)
        client.post("/api/v1/simulations", json=config_payload(risk_b["id"]), headers=manager_headers)

        scenario = client.post(
            "/api/v1/scenarios", json={"name": "Regional outage"}, headers=manager_headers
        ).json()
        client.post(f"/api/v1/scenarios/{scenario['id']}/risks", params={"risk_id": risk_a["id"]}, headers=manager_headers)
        client.post(f"/api/v1/scenarios/{scenario['id']}/risks", params={"risk_id": risk_b["id"]}, headers=manager_headers)

        run = client.post(
            "/api/v1/simulations/portfolio",
            json={"scenario_id": scenario["id"], "iterations": 300, "seed": 5},
            headers=manager_headers,
        ).json()

        while process_one():
            pass  # drain the queue: two single-risk configs were also enqueued above

        result = client.get(f"/api/v1/simulations/{run['id']}", headers=manager_headers).json()
        assert result["status"] == "succeeded"
        assert result["result"]["per_risk_contribution"] is not None
        assert set(result["result"]["per_risk_contribution"].keys()) == {risk_a["id"], risk_b["id"]}

    def test_portfolio_run_fails_when_a_linked_risk_has_no_config(self, client):
        manager_headers = login(client, "risk.manager@example.com")
        risk = create_risk(client, manager_headers)

        scenario = client.post(
            "/api/v1/scenarios", json={"name": "Underconfigured scenario"}, headers=manager_headers
        ).json()
        client.post(f"/api/v1/scenarios/{scenario['id']}/risks", params={"risk_id": risk["id"]}, headers=manager_headers)

        run = client.post(
            "/api/v1/simulations/portfolio",
            json={"scenario_id": scenario["id"], "iterations": 200, "seed": 1},
            headers=manager_headers,
        ).json()

        assert process_one() is True

        result = client.get(f"/api/v1/simulations/{run['id']}", headers=manager_headers).json()
        assert result["status"] == "failed"
        assert "no simulation config" in result["error"]
