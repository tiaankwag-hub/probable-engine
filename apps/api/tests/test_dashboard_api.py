from apps.api.tests.conftest import login


def create_risk(client, headers, *, title, financial=3, likelihood=3, control_effectiveness=3,
                 category_id=None, next_review_date=None, decision="treat", status="open"):
    payload = {
        "title": title,
        "status": status,
        "decision": decision,
        "category_id": category_id,
        "next_review_date": next_review_date,
        "assessment": {
            "likelihood": likelihood,
            "impact_scores": {
                "financial": financial,
                "customer_service": financial,
                "operational_delivery": financial,
                "legal_regulatory": financial,
                "reputation": financial,
                "health_safety": financial,
            },
            "control_effectiveness": control_effectiveness,
        },
    }
    response = client.post("/api/v1/risks", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


class TestExecutiveDashboard:
    def test_empty_dashboard(self, client):
        headers = login(client, "executive@example.com")
        response = client.get("/api/v1/dashboard/executive", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["total_risks"] == 0
        assert len(body["heatmap"]) == 25

    def test_counts_and_bands_reflect_created_risks(self, client):
        headers = login(client, "risk.manager@example.com")
        create_risk(client, headers, title="Extreme risk", financial=5, likelihood=5, control_effectiveness=None)
        create_risk(client, headers, title="Low risk", financial=1, likelihood=1, control_effectiveness=5)

        response = client.get("/api/v1/dashboard/executive", headers=headers)
        body = response.json()
        assert body["total_risks"] == 2
        assert body["extreme_count"] == 1
        assert body["low_count"] == 1

    def test_closed_risks_excluded_from_counts(self, client):
        headers = login(client, "risk.manager@example.com")
        create_risk(client, headers, title="Closed risk", status="closed")
        create_risk(client, headers, title="Open risk", status="open")

        response = client.get("/api/v1/dashboard/executive", headers=headers)
        body = response.json()
        assert body["total_risks"] == 1

    def test_overdue_review_detected(self, client):
        headers = login(client, "risk.manager@example.com")
        create_risk(client, headers, title="Overdue risk", next_review_date="2000-01-01")
        create_risk(client, headers, title="Future risk", next_review_date="2099-01-01")

        response = client.get("/api/v1/dashboard/executive", headers=headers)
        body = response.json()
        assert body["overdue_reviews_count"] == 1

    def test_heatmap_places_risk_in_correct_cell(self, client):
        headers = login(client, "risk.manager@example.com")
        create_risk(client, headers, title="Grid risk", financial=4, likelihood=2, control_effectiveness=None)

        response = client.get("/api/v1/dashboard/executive", headers=headers)
        body = response.json()
        cell = next(c for c in body["heatmap"] if c["likelihood"] == 2 and c["impact"] == 4)
        assert cell["count"] == 1
        total_count = sum(c["count"] for c in body["heatmap"])
        assert total_count == 1

    def test_top_risks_ranked_by_residual_score_desc(self, client):
        headers = login(client, "risk.manager@example.com")
        create_risk(client, headers, title="Lower", financial=2, likelihood=2, control_effectiveness=5)
        create_risk(client, headers, title="Higher", financial=5, likelihood=5, control_effectiveness=None)

        response = client.get("/api/v1/dashboard/executive", headers=headers)
        top_risks = response.json()["top_risks"]
        assert top_risks[0]["title"] == "Higher"
        assert top_risks[0]["residual_score"] >= top_risks[1]["residual_score"]

    def test_category_exposure_grouped_by_category(self, client):
        headers = login(client, "risk.manager@example.com")
        categories = client.get(
            "/api/v1/risk-categories", headers=login(client, "viewer@example.com")
        ).json()
        operational = next(c for c in categories if c["name"] == "Operational")
        create_risk(client, headers, title="Op risk 1", category_id=operational["id"])
        create_risk(client, headers, title="Op risk 2", category_id=operational["id"])
        create_risk(client, headers, title="Uncategorized risk")

        response = client.get("/api/v1/dashboard/executive", headers=headers)
        exposure = response.json()["category_exposure"]
        op_entry = next(e for e in exposure if e["category_name"] == "Operational")
        assert op_entry["risk_count"] == 2
        uncategorized_entry = next(e for e in exposure if e["category_name"] == "Uncategorized")
        assert uncategorized_entry["risk_count"] == 1

    def test_dashboard_requires_authentication(self, client):
        response = client.get("/api/v1/dashboard/executive")
        assert response.status_code == 401
