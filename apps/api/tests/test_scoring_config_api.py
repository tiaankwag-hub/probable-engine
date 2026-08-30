from apps.api.tests.conftest import login

VALID_PAYLOAD = {
    "dimension_weights": {
        "financial": 0.3,
        "customer_service": 0.15,
        "operational_delivery": 0.15,
        "legal_regulatory": 0.15,
        "reputation": 0.15,
        "health_safety": 0.1,
    },
    "band_thresholds": [[5.0, "low"], [10.0, "moderate"], [15.0, "high"], [25.0, "extreme"]],
    "max_reduction_fraction": 0.5,
    "max_control_effectiveness": 5,
}


class TestScoringConfigList:
    def test_seeded_config_is_active_version_1(self, client):
        headers = login(client, "viewer@example.com")
        response = client.get("/api/v1/scoring-config", headers=headers)
        assert response.status_code == 200
        configs = response.json()
        assert len(configs) == 1
        assert configs[0]["version"] == 1
        assert configs[0]["is_active"] is True

    def test_requires_authentication(self, client):
        response = client.get("/api/v1/scoring-config")
        assert response.status_code == 401


class TestScoringConfigCreate:
    def test_administrator_can_create_new_version(self, client):
        headers = login(client, "admin@example.com")
        response = client.post("/api/v1/scoring-config", json=VALID_PAYLOAD, headers=headers)
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["version"] == 2
        assert body["is_active"] is True

    def test_new_version_deactivates_previous(self, client):
        headers = login(client, "admin@example.com")
        client.post("/api/v1/scoring-config", json=VALID_PAYLOAD, headers=headers)

        list_response = client.get("/api/v1/scoring-config", headers=headers)
        configs = {c["version"]: c["is_active"] for c in list_response.json()}
        assert configs[1] is False
        assert configs[2] is True

    def test_non_administrator_roles_forbidden(self, client):
        for email in [
            "viewer@example.com",
            "risk.owner@example.com",
            "risk.manager@example.com",
            "control.owner@example.com",
            "executive@example.com",
            "auditor@example.com",
        ]:
            headers = login(client, email)
            response = client.post("/api/v1/scoring-config", json=VALID_PAYLOAD, headers=headers)
            assert response.status_code == 403, f"{email} should not manage scoring config"

    def test_weights_not_summing_to_one_rejected(self, client):
        headers = login(client, "admin@example.com")
        bad_payload = dict(VALID_PAYLOAD)
        bad_payload["dimension_weights"] = {**VALID_PAYLOAD["dimension_weights"], "financial": 0.9}
        response = client.post("/api/v1/scoring-config", json=bad_payload, headers=headers)
        assert response.status_code == 422

    def test_unsorted_thresholds_rejected(self, client):
        headers = login(client, "admin@example.com")
        bad_payload = dict(VALID_PAYLOAD)
        bad_payload["band_thresholds"] = [[10.0, "moderate"], [5.0, "low"]]
        response = client.post("/api/v1/scoring-config", json=bad_payload, headers=headers)
        assert response.status_code == 422

    def test_new_config_affects_subsequent_risk_scoring_not_past_assessments(self, client):
        headers = login(client, "admin@example.com")

        # Create a risk under the seeded (version 1) config.
        create_response = client.post(
            "/api/v1/risks",
            json={
                "title": "Pre-config-change risk",
                "assessment": {
                    "likelihood": 3,
                    "impact_scores": {
                        "financial": 3, "customer_service": 3, "operational_delivery": 3,
                        "legal_regulatory": 3, "reputation": 3, "health_safety": 3,
                    },
                    "control_effectiveness": 3,
                },
            },
            headers=headers,
        )
        risk = create_response.json()
        history_before = client.get(f"/api/v1/risks/{risk['id']}/history", headers=headers).json()
        assert history_before[0]["field_state"]["overall_impact"] == 3.0

        # Install a new active config that heavily weights financial impact.
        client.post("/api/v1/scoring-config", json=VALID_PAYLOAD, headers=headers)

        # Reassess the same risk — should now use the new config's weights.
        patch_response = client.patch(
            f"/api/v1/risks/{risk['id']}",
            json={
                "version": risk["version"],
                "assessment": {
                    "likelihood": 3,
                    "impact_scores": {
                        "financial": 5, "customer_service": 1, "operational_delivery": 1,
                        "legal_regulatory": 1, "reputation": 1, "health_safety": 1,
                    },
                    "control_effectiveness": 3,
                },
            },
            headers=headers,
        )
        assert patch_response.status_code == 200
        updated = patch_response.json()
        # weighted: 5*0.3 + 1*0.15*4 + 1*0.1 = 1.5 + 0.6 + 0.1 = 2.2
        assert updated["overall_impact"] == 2.2
