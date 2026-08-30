from datetime import date, timedelta

from apps.api.tests.conftest import login


def create_risk(client, headers, *, title, financial=5, likelihood=5, control_effectiveness=None):
    payload = {
        "title": title,
        "assessment": {
            "likelihood": likelihood,
            "impact_scores": {
                "financial": financial, "customer_service": financial, "operational_delivery": financial,
                "legal_regulatory": financial, "reputation": financial, "health_safety": financial,
            },
            "control_effectiveness": control_effectiveness,
        },
    }
    response = client.post("/api/v1/risks", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


class TestGovernanceHealth:
    def test_requires_authentication(self, client):
        response = client.get("/api/v1/dashboard/governance")
        assert response.status_code == 401

    def test_weak_controls_counted(self, client):
        control_headers = login(client, "control.owner@example.com")
        client.post(
            "/api/v1/controls",
            json={
                "name": "Weak control",
                "control_type": "detective",
                "automation": "manual",
                "operating_effectiveness": 1,
            },
            headers=control_headers,
        )
        client.post(
            "/api/v1/controls",
            json={
                "name": "Strong control",
                "control_type": "detective",
                "automation": "manual",
                "operating_effectiveness": 5,
            },
            headers=control_headers,
        )

        response = client.get("/api/v1/dashboard/governance", headers=control_headers)
        body = response.json()
        assert body["weak_controls_count"] == 1
        assert body["weak_controls"][0]["name"] == "Weak control"

    def test_overdue_actions_counted(self, client):
        headers = login(client, "risk.owner@example.com")
        overdue_date = (date.today() - timedelta(days=3)).isoformat()
        client.post(
            "/api/v1/actions", json={"title": "Late action", "due_date": overdue_date}, headers=headers
        )

        response = client.get("/api/v1/dashboard/governance", headers=headers)
        body = response.json()
        assert body["overdue_actions_count"] == 1
        assert body["overdue_actions"][0]["title"] == "Late action"

    def test_overdue_reviews_counted(self, client):
        headers = login(client, "risk.owner@example.com")
        create_risk(client, headers, title="Overdue review risk")
        # Force an overdue next_review_date via update
        risks = client.get("/api/v1/risks", headers=headers).json()
        risk = next(r for r in risks if r["title"] == "Overdue review risk")
        client.patch(
            f"/api/v1/risks/{risk['id']}",
            json={"version": risk["version"], "next_review_date": "2000-01-01"},
            headers=headers,
        )

        response = client.get("/api/v1/dashboard/governance", headers=headers)
        assert response.json()["overdue_reviews_count"] == 1

    def test_appetite_breach_detected(self, client):
        admin_headers = login(client, "admin@example.com")
        client.post(
            "/api/v1/risk-appetite",
            json={
                "category_id": None,
                "business_unit": None,
                "appetite_band": "low",
                "tolerance_band": "low",
                "limit_value": None,
                "effective_from": "2020-01-01",
                "effective_to": None,
            },
            headers=admin_headers,
        )

        owner_headers = login(client, "risk.owner@example.com")
        create_risk(client, owner_headers, title="Extreme uncontrolled risk", financial=5, likelihood=5)

        response = client.get("/api/v1/dashboard/governance", headers=owner_headers)
        body = response.json()
        assert body["appetite_status_counts"].get("outside_appetite", 0) >= 1
        breach_titles = [r["title"] for r in body["breach_risks"]]
        assert "Extreme uncontrolled risk" in breach_titles

    def test_dashboard_executive_includes_governance_kpis(self, client):
        control_headers = login(client, "control.owner@example.com")
        client.post(
            "/api/v1/controls",
            json={
                "name": "Weak control",
                "control_type": "detective",
                "automation": "manual",
                "operating_effectiveness": 1,
            },
            headers=control_headers,
        )
        response = client.get("/api/v1/dashboard/executive", headers=control_headers)
        body = response.json()
        assert "weak_controls_count" in body
        assert body["weak_controls_count"] == 1
        assert "overdue_actions_count" in body
        assert "risks_outside_appetite_count" in body
