from apps.api.tests.conftest import login
from apps.worker.app.main import process_one


def create_risk(client, headers, title="AI-analyzed risk", likelihood=3, control_effectiveness=3):
    payload = {
        "title": title,
        "assessment": {
            "likelihood": likelihood,
            "impact_scores": {
                "financial": 3, "customer_service": 3, "operational_delivery": 3,
                "legal_regulatory": 3, "reputation": 3, "health_safety": 3,
            },
            "control_effectiveness": control_effectiveness,
        },
    }
    response = client.post("/api/v1/risks", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


class TestExecutiveSummary:
    def test_allowed_roles_can_request(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        for email in ["risk.manager@example.com", "executive@example.com", "admin@example.com"]:
            headers = login(client, email)
            response = client.post("/api/v1/ai/executive-summary", headers=headers)
            assert response.status_code == 202, f"{email}: {response.text}"
            assert response.json()["status"] == "pending"

    def test_forbidden_roles_cannot_request(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        for email in ["viewer@example.com", "risk.owner@example.com", "control.owner@example.com", "auditor@example.com"]:
            headers = login(client, email)
            response = client.post("/api/v1/ai/executive-summary", headers=headers)
            assert response.status_code == 403, f"{email} should not request executive summary"

    def test_completes_using_mock_provider(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        headers = login(client, "executive@example.com")
        run = client.post("/api/v1/ai/executive-summary", headers=headers).json()

        assert process_one() is True

        response = client.get(f"/api/v1/ai/runs/{run['id']}", headers=headers)
        body = response.json()
        assert body["status"] == "succeeded"
        assert body["narrative"]
        assert body["model"] == "mock-analyst-v1"


class TestRiskAnalysis:
    def test_risk_owner_can_analyze_own_risk(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        headers = login(client, "risk.owner@example.com")
        risk = create_risk(client, headers)
        response = client.post("/api/v1/ai/risk-analysis", json={"risk_id": risk["id"]}, headers=headers)
        assert response.status_code == 202, response.text

    def test_risk_owner_cannot_analyze_someone_elses_risk(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        owner_headers = login(client, "risk.owner@example.com")
        risk = create_risk(client, owner_headers)

        other_headers = login(client, "control.owner@example.com")
        response = client.post("/api/v1/ai/risk-analysis", json={"risk_id": risk["id"]}, headers=other_headers)
        assert response.status_code == 403

    def test_risk_manager_can_analyze_any_risk(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        owner_headers = login(client, "risk.owner@example.com")
        risk = create_risk(client, owner_headers)

        manager_headers = login(client, "risk.manager@example.com")
        response = client.post("/api/v1/ai/risk-analysis", json={"risk_id": risk["id"]}, headers=manager_headers)
        assert response.status_code == 202

    def test_unknown_risk_is_404(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        headers = login(client, "risk.manager@example.com")
        response = client.post(
            "/api/v1/ai/risk-analysis",
            json={"risk_id": "00000000-0000-0000-0000-000000000000"},
            headers=headers,
        )
        assert response.status_code == 404


class TestRunVisibility:
    def test_unknown_run_is_404(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        headers = login(client, "risk.manager@example.com")
        response = client.get("/api/v1/ai/runs/00000000-0000-0000-0000-000000000000", headers=headers)
        assert response.status_code == 404

    def test_control_owner_cannot_view_any_ai_run(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        manager_headers = login(client, "risk.manager@example.com")
        run = client.post("/api/v1/ai/executive-summary", headers=manager_headers).json()

        control_owner_headers = login(client, "control.owner@example.com")
        response = client.get(f"/api/v1/ai/runs/{run['id']}", headers=control_owner_headers)
        assert response.status_code == 403


class TestSuggestionReview:
    def test_full_approve_flow_applies_change_via_update_risk(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        owner_headers = login(client, "risk.owner@example.com")
        risk = create_risk(client, owner_headers, likelihood=3)

        # Give the risk a recent incident so the mock provider proposes a change.
        incident_response = client.post(
            "/api/v1/incidents",
            json={
                "risk_id": risk["id"], "description": "Outage", "incident_date": "2026-01-01",
                "severity": "high",
            },
            headers=owner_headers,
        )
        assert incident_response.status_code == 201, incident_response.text

        run = client.post(
            "/api/v1/ai/risk-analysis", json={"risk_id": risk["id"]}, headers=owner_headers
        ).json()
        assert process_one() is True

        run_detail = client.get(f"/api/v1/ai/runs/{run['id']}", headers=owner_headers).json()
        assert len(run_detail["suggestions"]) == 1
        suggestion = run_detail["suggestions"][0]
        assert suggestion["proposed_changes"] == {"likelihood": 4}

        manager_headers = login(client, "risk.manager@example.com")
        approve_response = client.post(
            f"/api/v1/ai/suggestions/{suggestion['id']}/approve", headers=manager_headers
        )
        assert approve_response.status_code == 200, approve_response.text
        assert approve_response.json()["human_review_status"] == "approved"

        updated_risk = client.get(f"/api/v1/risks/{risk['id']}", headers=manager_headers).json()
        assert updated_risk["likelihood"] == 4
        assert updated_risk["version"] == 2

        history = client.get(f"/api/v1/risks/{risk['id']}/history", headers=manager_headers).json()
        assert len(history) == 2

    def test_risk_owner_cannot_approve(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        owner_headers = login(client, "risk.owner@example.com")
        risk = create_risk(client, owner_headers)
        client.post(
            "/api/v1/incidents",
            json={"risk_id": risk["id"], "description": "x", "incident_date": "2026-01-01", "severity": "high"},
            headers=owner_headers,
        )
        run = client.post(
            "/api/v1/ai/risk-analysis", json={"risk_id": risk["id"]}, headers=owner_headers
        ).json()
        process_one()
        run_detail = client.get(f"/api/v1/ai/runs/{run['id']}", headers=owner_headers).json()
        suggestion_id = run_detail["suggestions"][0]["id"]

        response = client.post(f"/api/v1/ai/suggestions/{suggestion_id}/approve", headers=owner_headers)
        assert response.status_code == 403

    def test_reject_leaves_risk_untouched(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        owner_headers = login(client, "risk.owner@example.com")
        risk = create_risk(client, owner_headers, likelihood=3)
        client.post(
            "/api/v1/incidents",
            json={"risk_id": risk["id"], "description": "x", "incident_date": "2026-01-01", "severity": "high"},
            headers=owner_headers,
        )
        run = client.post(
            "/api/v1/ai/risk-analysis", json={"risk_id": risk["id"]}, headers=owner_headers
        ).json()
        process_one()
        run_detail = client.get(f"/api/v1/ai/runs/{run['id']}", headers=owner_headers).json()
        suggestion_id = run_detail["suggestions"][0]["id"]

        manager_headers = login(client, "risk.manager@example.com")
        response = client.post(f"/api/v1/ai/suggestions/{suggestion_id}/reject", headers=manager_headers)
        assert response.status_code == 200
        assert response.json()["human_review_status"] == "rejected"

        unchanged_risk = client.get(f"/api/v1/risks/{risk['id']}", headers=manager_headers).json()
        assert unchanged_risk["likelihood"] == 3
        assert unchanged_risk["version"] == 1

    def test_cannot_review_a_suggestion_twice(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        owner_headers = login(client, "risk.owner@example.com")
        risk = create_risk(client, owner_headers)
        client.post(
            "/api/v1/incidents",
            json={"risk_id": risk["id"], "description": "x", "incident_date": "2026-01-01", "severity": "high"},
            headers=owner_headers,
        )
        run = client.post(
            "/api/v1/ai/risk-analysis", json={"risk_id": risk["id"]}, headers=owner_headers
        ).json()
        process_one()
        run_detail = client.get(f"/api/v1/ai/runs/{run['id']}", headers=owner_headers).json()
        suggestion_id = run_detail["suggestions"][0]["id"]

        manager_headers = login(client, "risk.manager@example.com")
        client.post(f"/api/v1/ai/suggestions/{suggestion_id}/reject", headers=manager_headers)
        second_response = client.post(
            f"/api/v1/ai/suggestions/{suggestion_id}/approve", headers=manager_headers
        )
        assert second_response.status_code == 409

    def test_pending_queue_restricted_to_approvers(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        owner_headers = login(client, "risk.owner@example.com")
        response = client.get("/api/v1/ai/suggestions", headers=owner_headers)
        assert response.status_code == 403

    def test_risk_owner_can_view_own_risk_suggestions(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        owner_headers = login(client, "risk.owner@example.com")
        risk = create_risk(client, owner_headers)
        client.post(
            "/api/v1/incidents",
            json={"risk_id": risk["id"], "description": "x", "incident_date": "2026-01-01", "severity": "high"},
            headers=owner_headers,
        )
        run = client.post(
            "/api/v1/ai/risk-analysis", json={"risk_id": risk["id"]}, headers=owner_headers
        ).json()
        process_one()

        response = client.get(
            "/api/v1/ai/suggestions", params={"risk_id": risk["id"]}, headers=owner_headers
        )
        assert response.status_code == 200
        assert len(response.json()) == 1


class TestControlGapAnalysis:
    def test_risk_owner_can_analyze_own_risk(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        headers = login(client, "risk.owner@example.com")
        risk = create_risk(client, headers)
        response = client.post(
            "/api/v1/ai/control-gap-analysis", json={"risk_id": risk["id"]}, headers=headers
        )
        assert response.status_code == 202, response.text

    def test_risk_owner_cannot_analyze_someone_elses_risk(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        owner_headers = login(client, "risk.owner@example.com")
        risk = create_risk(client, owner_headers)

        other_headers = login(client, "control.owner@example.com")
        response = client.post(
            "/api/v1/ai/control-gap-analysis", json={"risk_id": risk["id"]}, headers=other_headers
        )
        assert response.status_code == 403

    def test_unknown_risk_is_404(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        headers = login(client, "risk.manager@example.com")
        response = client.post(
            "/api/v1/ai/control-gap-analysis",
            json={"risk_id": "00000000-0000-0000-0000-000000000000"},
            headers=headers,
        )
        assert response.status_code == 404

    def test_no_linked_controls_produces_a_new_control_suggestion_and_approving_creates_it(
        self, client, monkeypatch
    ):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        owner_headers = login(client, "risk.owner@example.com")
        risk = create_risk(client, owner_headers)

        run = client.post(
            "/api/v1/ai/control-gap-analysis", json={"risk_id": risk["id"]}, headers=owner_headers
        ).json()
        assert process_one() is True

        run_detail = client.get(f"/api/v1/ai/runs/{run['id']}", headers=owner_headers).json()
        assert len(run_detail["suggestions"]) == 1
        suggestion = run_detail["suggestions"][0]
        assert suggestion["suggestion_type"] == "new_control"
        assert suggestion["risk_id"] == risk["id"]

        manager_headers = login(client, "risk.manager@example.com")
        approve_response = client.post(
            f"/api/v1/ai/suggestions/{suggestion['id']}/approve", headers=manager_headers
        )
        assert approve_response.status_code == 200, approve_response.text

        linked_controls = client.get(
            f"/api/v1/risks/{risk['id']}/controls", headers=manager_headers
        ).json()
        assert len(linked_controls) == 1
        assert linked_controls[0]["name"] == suggestion["proposed_changes"]["name"]
        assert linked_controls[0]["control_type"] == suggestion["proposed_changes"]["control_type"]


class TestEmergingRiskScan:
    def test_allowed_roles_can_request(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        for email in ["risk.manager@example.com", "admin@example.com"]:
            headers = login(client, email)
            response = client.post("/api/v1/ai/emerging-risks", headers=headers)
            assert response.status_code == 202, f"{email}: {response.text}"

    def test_forbidden_roles_cannot_request(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        for email in [
            "viewer@example.com", "risk.owner@example.com", "control.owner@example.com",
            "executive@example.com", "auditor@example.com",
        ]:
            headers = login(client, email)
            response = client.post("/api/v1/ai/emerging-risks", headers=headers)
            assert response.status_code == 403, f"{email} should not request an emerging-risk scan"

    def test_approving_a_new_risk_suggestion_creates_an_unassessed_placeholder_risk(
        self, client, monkeypatch
    ):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        manager_headers = login(client, "risk.manager@example.com")
        run = client.post("/api/v1/ai/emerging-risks", headers=manager_headers).json()
        assert process_one() is True

        run_detail = client.get(f"/api/v1/ai/runs/{run['id']}", headers=manager_headers).json()
        assert len(run_detail["suggestions"]) == 1
        suggestion = run_detail["suggestions"][0]
        assert suggestion["suggestion_type"] == "new_risk"
        assert suggestion["risk_id"] is None

        approve_response = client.post(
            f"/api/v1/ai/suggestions/{suggestion['id']}/approve", headers=manager_headers
        )
        assert approve_response.status_code == 200, approve_response.text

        proposed_title = suggestion["proposed_changes"]["title"]
        matches = client.get(
            "/api/v1/risks", params={"q": proposed_title}, headers=manager_headers
        ).json()
        assert len(matches) == 1
        created_risk = matches[0]
        assert created_risk["title"] == proposed_title
        assert created_risk["status"] == "draft"
        assert created_risk["likelihood"] == 1


class TestMarketAnalysis:
    def test_allowed_roles_can_request(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        for email in ["risk.manager@example.com", "executive@example.com", "admin@example.com"]:
            headers = login(client, email)
            response = client.post("/api/v1/ai/market-analysis", headers=headers)
            assert response.status_code == 202, f"{email}: {response.text}"

    def test_forbidden_roles_cannot_request(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        for email in ["viewer@example.com", "risk.owner@example.com", "control.owner@example.com", "auditor@example.com"]:
            headers = login(client, email)
            response = client.post("/api/v1/ai/market-analysis", headers=headers)
            assert response.status_code == 403, f"{email} should not request market analysis"

    def test_completes_and_never_produces_a_suggestion(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        headers = login(client, "executive@example.com")
        run = client.post("/api/v1/ai/market-analysis", headers=headers).json()
        assert process_one() is True

        run_detail = client.get(f"/api/v1/ai/runs/{run['id']}", headers=headers).json()
        assert run_detail["status"] == "succeeded"
        assert run_detail["narrative"]
        assert run_detail["suggestions"] == []
