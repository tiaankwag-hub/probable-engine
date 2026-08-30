from apps.api.tests.conftest import login


def make_risk_payload(**overrides):
    payload = {
        "title": "Test risk",
        "statement": "A test risk statement",
        "status": "open",
        "decision": "treat",
        "assessment": {
            "likelihood": 3,
            "impact_scores": {
                "financial": 3,
                "customer_service": 3,
                "operational_delivery": 3,
                "legal_regulatory": 3,
                "reputation": 3,
                "health_safety": 3,
            },
            "control_effectiveness": 3,
        },
    }
    payload.update(overrides)
    return payload


class TestAuth:
    def test_no_token_is_unauthorized(self, client):
        response = client.get("/api/v1/risks")
        assert response.status_code == 401

    def test_bad_token_is_unauthorized(self, client):
        response = client.get("/api/v1/risks", headers={"Authorization": "Bearer not-a-uuid"})
        assert response.status_code == 401

    def test_mock_login_returns_roles(self, client):
        response = client.post(
            "/api/v1/auth/mock-login", json={"email": "risk.manager@example.com"}
        )
        assert response.status_code == 200
        assert response.json()["roles"] == ["risk_manager"]


class TestRiskCreate:
    def test_viewer_cannot_create_risk(self, client):
        headers = login(client, "viewer@example.com")
        response = client.post("/api/v1/risks", json=make_risk_payload(), headers=headers)
        assert response.status_code == 403

    def test_risk_owner_can_create_risk(self, client):
        headers = login(client, "risk.owner@example.com")
        response = client.post("/api/v1/risks", json=make_risk_payload(), headers=headers)
        assert response.status_code == 201
        body = response.json()
        assert body["risk_code"].startswith("RSK-")
        assert body["overall_impact"] == 3.0
        assert body["inherent_score"] == 9.0
        assert body["version"] == 1

    def test_accept_without_rationale_is_rejected(self, client):
        headers = login(client, "risk.owner@example.com")
        response = client.post(
            "/api/v1/risks", json=make_risk_payload(decision="accept"), headers=headers
        )
        assert response.status_code == 422

    def test_accept_with_rationale_is_accepted(self, client):
        headers = login(client, "risk.owner@example.com")
        response = client.post(
            "/api/v1/risks",
            json=make_risk_payload(decision="accept", acceptance_rationale="within appetite"),
            headers=headers,
        )
        assert response.status_code == 201

    def test_invalid_impact_score_is_rejected_by_schema(self, client):
        headers = login(client, "risk.owner@example.com")
        payload = make_risk_payload()
        payload["assessment"]["impact_scores"]["financial"] = 9
        response = client.post("/api/v1/risks", json=payload, headers=headers)
        assert response.status_code == 422


class TestRiskReadUpdate:
    def _create(self, client, **overrides):
        headers = login(client, "risk.owner@example.com")
        response = client.post("/api/v1/risks", json=make_risk_payload(**overrides), headers=headers)
        assert response.status_code == 201
        return response.json(), headers

    def test_get_risk_detail(self, client):
        created, headers = self._create(client)
        response = client.get(f"/api/v1/risks/{created['id']}", headers=headers)
        assert response.status_code == 200
        assert response.json()["risk_code"] == created["risk_code"]

    def test_get_missing_risk_is_404(self, client):
        headers = login(client, "risk.owner@example.com")
        response = client.get(
            "/api/v1/risks/00000000-0000-0000-0000-000000000000", headers=headers
        )
        assert response.status_code == 404

    def test_list_risks_returns_total_count_header(self, client):
        self._create(client, title="Risk A")
        self._create(client, title="Risk B")
        headers = login(client, "viewer@example.com")
        response = client.get("/api/v1/risks", headers=headers)
        assert response.status_code == 200
        assert response.headers["X-Total-Count"] == "2"
        assert len(response.json()) == 2

    def test_list_risks_search_filter(self, client):
        self._create(client, title="Vendor outage risk")
        self._create(client, title="Unrelated risk")
        headers = login(client, "viewer@example.com")
        response = client.get("/api/v1/risks", params={"q": "Vendor"}, headers=headers)
        assert len(response.json()) == 1
        assert response.json()[0]["title"] == "Vendor outage risk"

    def test_update_risk_bumps_version_and_recomputes_score(self, client):
        created, headers = self._create(client)
        payload = {
            "version": created["version"],
            "assessment": {
                "likelihood": 5,
                "impact_scores": {
                    "financial": 5, "customer_service": 5, "operational_delivery": 5,
                    "legal_regulatory": 5, "reputation": 5, "health_safety": 5,
                },
                "control_effectiveness": None,
            },
        }
        response = client.patch(f"/api/v1/risks/{created['id']}", json=payload, headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["version"] == 2
        assert body["inherent_score"] == 25.0
        assert body["inherent_band"] == "extreme"

    def test_update_with_stale_version_is_conflict(self, client):
        created, headers = self._create(client)
        payload = {"version": created["version"] + 5, "title": "changed"}
        response = client.patch(f"/api/v1/risks/{created['id']}", json=payload, headers=headers)
        assert response.status_code == 409

    def test_update_creates_history_entry(self, client):
        created, headers = self._create(client)
        client.patch(
            f"/api/v1/risks/{created['id']}",
            json={"version": created["version"], "title": "renamed"},
            headers=headers,
        )
        response = client.get(f"/api/v1/risks/{created['id']}/history", headers=headers)
        assert response.status_code == 200
        history = response.json()
        assert len(history) == 2
        assert history[0]["version"] == 2
        assert history[0]["field_state"]["title"] == "renamed"

    def test_risk_owner_cannot_edit_others_risk(self, client):
        manager_headers = login(client, "risk.manager@example.com")
        create_response = client.post(
            "/api/v1/risks", json=make_risk_payload(), headers=manager_headers
        )
        risk = create_response.json()

        owner_headers = login(client, "risk.owner@example.com")
        response = client.patch(
            f"/api/v1/risks/{risk['id']}",
            json={"version": risk["version"], "title": "hijacked"},
            headers=owner_headers,
        )
        assert response.status_code == 403

    def test_risk_manager_can_edit_any_risk(self, client):
        owner_headers = login(client, "risk.owner@example.com")
        create_response = client.post(
            "/api/v1/risks", json=make_risk_payload(), headers=owner_headers
        )
        risk = create_response.json()

        manager_headers = login(client, "risk.manager@example.com")
        response = client.patch(
            f"/api/v1/risks/{risk['id']}",
            json={"version": risk["version"], "title": "reassigned edit"},
            headers=manager_headers,
        )
        assert response.status_code == 200
        assert response.json()["title"] == "reassigned edit"
