from apps.api.tests.conftest import login
from apps.worker.app.main import process_one


def create_risk(client, headers, title="Existing risk"):
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


def ingest_and_process(client, headers):
    response = client.post("/api/v1/emerging-risks/ingest", headers=headers)
    assert response.status_code == 202, response.text
    assert process_one() is True
    return response.json()["job_id"]


class TestIngest:
    def test_allowed_roles_can_ingest(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        for email in ["risk.manager@example.com", "admin@example.com"]:
            headers = login(client, email)
            response = client.post("/api/v1/emerging-risks/ingest", headers=headers)
            assert response.status_code == 202, f"{email}: {response.text}"

    def test_forbidden_roles_cannot_ingest(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        for email in [
            "viewer@example.com", "risk.owner@example.com", "control.owner@example.com",
            "executive@example.com", "auditor@example.com",
        ]:
            headers = login(client, email)
            response = client.post("/api/v1/emerging-risks/ingest", headers=headers)
            assert response.status_code == 403, f"{email} should not be able to ingest"

    def test_job_completes_and_produces_candidates(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        headers = login(client, "risk.manager@example.com")
        job_id = ingest_and_process(client, headers)

        job = client.get(f"/api/v1/jobs/{job_id}", headers=headers).json()
        assert job["status"] == "succeeded"

        candidates = client.get("/api/v1/emerging-risks", headers=headers).json()
        assert len(candidates) == 5
        assert all(c["lifecycle_status"] == "candidate" for c in candidates)
        assert all(c["model"] == "mock-analyst-v1" for c in candidates)
        assert all(len(c["signals"]) >= 1 for c in candidates)


class TestListAndViewRbac:
    def test_allowed_roles_can_view(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        manager_headers = login(client, "risk.manager@example.com")
        ingest_and_process(client, manager_headers)

        for email in ["risk.owner@example.com", "risk.manager@example.com", "executive@example.com", "admin@example.com"]:
            headers = login(client, email)
            response = client.get("/api/v1/emerging-risks", headers=headers)
            assert response.status_code == 200, f"{email}: {response.text}"

    def test_forbidden_roles_cannot_view(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        for email in ["viewer@example.com", "control.owner@example.com", "auditor@example.com"]:
            headers = login(client, email)
            response = client.get("/api/v1/emerging-risks", headers=headers)
            assert response.status_code == 403, f"{email} should not be able to view emerging risks"

    def test_filter_by_lifecycle_status(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        headers = login(client, "risk.manager@example.com")
        ingest_and_process(client, headers)

        response = client.get(
            "/api/v1/emerging-risks", params={"lifecycle_status": "candidate"}, headers=headers
        )
        assert response.status_code == 200
        assert len(response.json()) == 5

        response = client.get(
            "/api/v1/emerging-risks", params={"lifecycle_status": "accepted"}, headers=headers
        )
        assert response.json() == []

    def test_unknown_candidate_is_404(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        headers = login(client, "risk.manager@example.com")
        response = client.get(
            "/api/v1/emerging-risks/00000000-0000-0000-0000-000000000000", headers=headers
        )
        assert response.status_code == 404


class TestLifecycleTransition:
    def test_accepting_a_candidate_creates_a_real_risk(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        manager_headers = login(client, "risk.manager@example.com")
        ingest_and_process(client, manager_headers)
        candidate = client.get("/api/v1/emerging-risks", headers=manager_headers).json()[0]

        response = client.patch(
            f"/api/v1/emerging-risks/{candidate['id']}",
            json={"lifecycle_status": "accepted"},
            headers=manager_headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["lifecycle_status"] == "accepted"
        assert body["created_risk_id"] is not None

        created_risk = client.get(f"/api/v1/risks/{body['created_risk_id']}", headers=manager_headers).json()
        assert created_risk["title"] == candidate["title"]
        assert created_risk["status"] == "draft"
        assert created_risk["likelihood"] == 1

    def test_dismissing_a_candidate_creates_no_risk(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        manager_headers = login(client, "risk.manager@example.com")
        ingest_and_process(client, manager_headers)
        candidate = client.get("/api/v1/emerging-risks", headers=manager_headers).json()[0]

        response = client.patch(
            f"/api/v1/emerging-risks/{candidate['id']}",
            json={"lifecycle_status": "dismissed"},
            headers=manager_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["lifecycle_status"] == "dismissed"
        assert body["created_risk_id"] is None

    def test_cannot_transition_a_finalized_candidate_again(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        manager_headers = login(client, "risk.manager@example.com")
        ingest_and_process(client, manager_headers)
        candidate = client.get("/api/v1/emerging-risks", headers=manager_headers).json()[0]
        client.patch(
            f"/api/v1/emerging-risks/{candidate['id']}",
            json={"lifecycle_status": "dismissed"},
            headers=manager_headers,
        )

        response = client.patch(
            f"/api/v1/emerging-risks/{candidate['id']}",
            json={"lifecycle_status": "accepted"},
            headers=manager_headers,
        )
        assert response.status_code == 409

    def test_cannot_transition_directly_to_linked_to_existing(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        manager_headers = login(client, "risk.manager@example.com")
        ingest_and_process(client, manager_headers)
        candidate = client.get("/api/v1/emerging-risks", headers=manager_headers).json()[0]

        response = client.patch(
            f"/api/v1/emerging-risks/{candidate['id']}",
            json={"lifecycle_status": "linked_to_existing"},
            headers=manager_headers,
        )
        assert response.status_code == 400

    def test_forbidden_roles_cannot_transition(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        manager_headers = login(client, "risk.manager@example.com")
        ingest_and_process(client, manager_headers)
        candidate = client.get("/api/v1/emerging-risks", headers=manager_headers).json()[0]

        owner_headers = login(client, "risk.owner@example.com")
        response = client.patch(
            f"/api/v1/emerging-risks/{candidate['id']}",
            json={"lifecycle_status": "accepted"},
            headers=owner_headers,
        )
        assert response.status_code == 403


class TestLinkExistingRisk:
    def test_links_and_marks_lifecycle_status(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        manager_headers = login(client, "risk.manager@example.com")
        existing_risk = create_risk(client, manager_headers)
        ingest_and_process(client, manager_headers)
        candidate = client.get("/api/v1/emerging-risks", headers=manager_headers).json()[0]

        response = client.post(
            f"/api/v1/emerging-risks/{candidate['id']}/link-existing-risk",
            json={"risk_id": existing_risk["id"]},
            headers=manager_headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["lifecycle_status"] == "linked_to_existing"
        assert body["matched_risk_id"] == existing_risk["id"]

    def test_unknown_risk_is_404(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        manager_headers = login(client, "risk.manager@example.com")
        ingest_and_process(client, manager_headers)
        candidate = client.get("/api/v1/emerging-risks", headers=manager_headers).json()[0]

        response = client.post(
            f"/api/v1/emerging-risks/{candidate['id']}/link-existing-risk",
            json={"risk_id": "00000000-0000-0000-0000-000000000000"},
            headers=manager_headers,
        )
        assert response.status_code == 404

    def test_forbidden_roles_cannot_link(self, client, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        manager_headers = login(client, "risk.manager@example.com")
        existing_risk = create_risk(client, manager_headers)
        ingest_and_process(client, manager_headers)
        candidate = client.get("/api/v1/emerging-risks", headers=manager_headers).json()[0]

        owner_headers = login(client, "risk.owner@example.com")
        response = client.post(
            f"/api/v1/emerging-risks/{candidate['id']}/link-existing-risk",
            json={"risk_id": existing_risk["id"]},
            headers=owner_headers,
        )
        assert response.status_code == 403
