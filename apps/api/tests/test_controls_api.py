from apps.api.tests.conftest import login


def make_control_payload(**overrides):
    payload = {
        "name": "Vendor concentration review",
        "control_type": "detective",
        "automation": "manual",
        "design_effectiveness": 3,
        "operating_effectiveness": 3,
        "status": "active",
    }
    payload.update(overrides)
    return payload


def create_control(client, headers, **overrides):
    response = client.post("/api/v1/controls", json=make_control_payload(**overrides), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


class TestControlCreate:
    def test_control_owner_can_create_control(self, client):
        headers = login(client, "control.owner@example.com")
        control = create_control(client, headers)
        assert control["control_code"].startswith("CTRL-")
        assert control["status"] == "active"

    def test_viewer_cannot_create_control(self, client):
        headers = login(client, "viewer@example.com")
        response = client.post("/api/v1/controls", json=make_control_payload(), headers=headers)
        assert response.status_code == 403

    def test_risk_owner_cannot_create_control(self, client):
        headers = login(client, "risk.owner@example.com")
        response = client.post("/api/v1/controls", json=make_control_payload(), headers=headers)
        assert response.status_code == 403


class TestControlOwnership:
    def test_control_owner_can_manage_own_control(self, client):
        headers = login(client, "control.owner@example.com")
        control = create_control(client, headers)
        response = client.patch(
            f"/api/v1/controls/{control['id']}",
            json=make_control_payload(design_effectiveness=4),
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["design_effectiveness"] == 4

    def test_control_owner_cannot_manage_others_control(self, client):
        owner_headers = login(client, "control.owner@example.com")
        control = create_control(client, owner_headers)

        manager_headers = login(client, "risk.manager@example.com")
        control2 = client.post(
            "/api/v1/controls",
            json=make_control_payload(name="Manager's own control", owner_id=None),
            headers=manager_headers,
        ).json()

        response = client.patch(
            f"/api/v1/controls/{control2['id']}", json=make_control_payload(), headers=owner_headers
        )
        assert response.status_code == 403

    def test_risk_manager_can_manage_any_control(self, client):
        owner_headers = login(client, "control.owner@example.com")
        control = create_control(client, owner_headers)

        manager_headers = login(client, "risk.manager@example.com")
        response = client.patch(
            f"/api/v1/controls/{control['id']}",
            json=make_control_payload(status="retired"),
            headers=manager_headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "retired"


class TestControlTests:
    def test_effective_result_sets_operating_effectiveness_to_5(self, client):
        headers = login(client, "control.owner@example.com")
        control = create_control(client, headers, operating_effectiveness=2)
        response = client.post(
            f"/api/v1/controls/{control['id']}/tests",
            json={
                "tester": "auditor@example.com",
                "test_date": "2026-01-15",
                "result": "effective",
            },
            headers=headers,
        )
        assert response.status_code == 201
        updated = client.get(f"/api/v1/controls/{control['id']}", headers=headers).json()
        assert updated["operating_effectiveness"] == 5
        assert updated["last_tested"] == "2026-01-15"

    def test_ineffective_result_sets_operating_effectiveness_to_1(self, client):
        headers = login(client, "control.owner@example.com")
        control = create_control(client, headers, operating_effectiveness=5)
        client.post(
            f"/api/v1/controls/{control['id']}/tests",
            json={"tester": "t", "test_date": "2026-02-01", "result": "ineffective"},
            headers=headers,
        )
        updated = client.get(f"/api/v1/controls/{control['id']}", headers=headers).json()
        assert updated["operating_effectiveness"] == 1

    def test_not_tested_result_leaves_effectiveness_unchanged(self, client):
        headers = login(client, "control.owner@example.com")
        control = create_control(client, headers, operating_effectiveness=4)
        client.post(
            f"/api/v1/controls/{control['id']}/tests",
            json={"tester": "t", "test_date": "2026-02-01", "result": "not_tested"},
            headers=headers,
        )
        updated = client.get(f"/api/v1/controls/{control['id']}", headers=headers).json()
        assert updated["operating_effectiveness"] == 4

    def test_list_control_tests(self, client):
        headers = login(client, "control.owner@example.com")
        control = create_control(client, headers)
        client.post(
            f"/api/v1/controls/{control['id']}/tests",
            json={"tester": "t", "test_date": "2026-01-01", "result": "effective"},
            headers=headers,
        )
        response = client.get(f"/api/v1/controls/{control['id']}/tests", headers=headers)
        assert response.status_code == 200
        assert len(response.json()) == 1


class TestRiskControlLinking:
    def _create_risk(self, client, headers):
        payload = {
            "title": "Risk needing a control",
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

    def test_link_and_list_control_on_risk(self, client):
        owner_headers = login(client, "risk.owner@example.com")
        risk = self._create_risk(client, owner_headers)

        control_headers = login(client, "control.owner@example.com")
        control = create_control(client, control_headers)

        link_response = client.post(
            f"/api/v1/risks/{risk['id']}/controls",
            json={"control_id": control["id"]},
            headers=owner_headers,
        )
        assert link_response.status_code == 201

        list_response = client.get(f"/api/v1/risks/{risk['id']}/controls", headers=owner_headers)
        assert len(list_response.json()) == 1
        assert list_response.json()[0]["id"] == control["id"]

    def test_cannot_link_control_to_risk_you_cannot_edit(self, client):
        manager_headers = login(client, "risk.manager@example.com")
        risk = self._create_risk(client, manager_headers)

        control_headers = login(client, "control.owner@example.com")
        control = create_control(client, control_headers)

        owner_headers = login(client, "risk.owner@example.com")
        response = client.post(
            f"/api/v1/risks/{risk['id']}/controls",
            json={"control_id": control["id"]},
            headers=owner_headers,
        )
        assert response.status_code == 403

    def test_unlink_control_from_risk(self, client):
        owner_headers = login(client, "risk.owner@example.com")
        risk = self._create_risk(client, owner_headers)
        control_headers = login(client, "control.owner@example.com")
        control = create_control(client, control_headers)
        client.post(
            f"/api/v1/risks/{risk['id']}/controls",
            json={"control_id": control["id"]},
            headers=owner_headers,
        )

        response = client.delete(
            f"/api/v1/risks/{risk['id']}/controls/{control['id']}", headers=owner_headers
        )
        assert response.status_code == 204

        list_response = client.get(f"/api/v1/risks/{risk['id']}/controls", headers=owner_headers)
        assert list_response.json() == []
