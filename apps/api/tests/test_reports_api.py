from apps.api.tests.conftest import login
from apps.worker.app.main import process_one

GENERATE_ALLOWED = ["risk.manager@example.com", "executive@example.com", "admin@example.com"]
GENERATE_FORBIDDEN = [
    "viewer@example.com",
    "risk.owner@example.com",
    "control.owner@example.com",
    "auditor@example.com",
]


class TestRequestReports:
    def test_allowed_roles_can_request_pdf(self, client):
        for email in GENERATE_ALLOWED:
            headers = login(client, email)
            response = client.post("/api/v1/reports/pdf", json={}, headers=headers)
            assert response.status_code == 202, f"{email}: {response.text}"
            body = response.json()
            assert body["report_type"] == "pdf_executive_summary"
            assert body["status"] == "pending"
            assert body["download_url"] is None

    def test_forbidden_roles_cannot_request_pdf(self, client):
        for email in GENERATE_FORBIDDEN:
            headers = login(client, email)
            response = client.post("/api/v1/reports/pdf", json={}, headers=headers)
            assert response.status_code == 403, f"{email} should not generate reports"

    def test_powerpoint_defaults_to_one_slide(self, client):
        headers = login(client, "risk.manager@example.com")
        response = client.post("/api/v1/reports/powerpoint", json={}, headers=headers)
        assert response.status_code == 202
        assert response.json()["report_type"] == "pptx_one_slide"

    def test_powerpoint_two_slide_elt_template(self, client):
        headers = login(client, "risk.manager@example.com")
        response = client.post(
            "/api/v1/reports/powerpoint", json={"template": "two_slide_elt"}, headers=headers
        )
        assert response.status_code == 202
        assert response.json()["report_type"] == "pptx_two_slide_elt"

    def test_request_enqueues_a_background_job(self, client, db_session, tmp_path, monkeypatch):
        monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
        headers = login(client, "risk.manager@example.com")
        response = client.post("/api/v1/reports/pdf", json={}, headers=headers)
        run_id = response.json()["id"]

        processed = process_one()
        assert processed is True

        run_response = client.get(f"/api/v1/reports/runs/{run_id}", headers=headers)
        assert run_response.json()["status"] == "succeeded"


class TestListAndGetReportRuns:
    def test_auditor_can_view_runs(self, client):
        manager_headers = login(client, "risk.manager@example.com")
        client.post("/api/v1/reports/pdf", json={}, headers=manager_headers)

        auditor_headers = login(client, "auditor@example.com")
        response = client.get("/api/v1/reports/runs", headers=auditor_headers)
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_risk_owner_cannot_view_runs(self, client):
        headers = login(client, "risk.owner@example.com")
        response = client.get("/api/v1/reports/runs", headers=headers)
        assert response.status_code == 403

    def test_unknown_run_is_404(self, client):
        headers = login(client, "risk.manager@example.com")
        response = client.get(
            "/api/v1/reports/runs/00000000-0000-0000-0000-000000000000", headers=headers
        )
        assert response.status_code == 404


class TestDownloadReportRun:
    def test_download_before_ready_is_400(self, client):
        headers = login(client, "risk.manager@example.com")
        run = client.post("/api/v1/reports/pdf", json={}, headers=headers).json()

        response = client.get(f"/api/v1/reports/runs/{run['id']}/download", headers=headers)
        assert response.status_code == 400

    def test_download_after_processing_returns_the_file(self, client, tmp_path, monkeypatch):
        monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
        headers = login(client, "risk.manager@example.com")
        run = client.post("/api/v1/reports/pdf", json={}, headers=headers).json()

        process_one()

        response = client.get(f"/api/v1/reports/runs/{run['id']}/download", headers=headers)
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.content.startswith(b"%PDF")

    def test_download_pptx_run_returns_pptx_content_type(self, client, tmp_path, monkeypatch):
        monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
        headers = login(client, "risk.manager@example.com")
        run = client.post("/api/v1/reports/powerpoint", json={}, headers=headers).json()

        process_one()

        response = client.get(f"/api/v1/reports/runs/{run['id']}/download", headers=headers)
        assert response.status_code == 200
        assert response.headers["content-type"] == (
            "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )

    def test_viewer_cannot_download(self, client, tmp_path, monkeypatch):
        monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
        manager_headers = login(client, "risk.manager@example.com")
        run = client.post("/api/v1/reports/pdf", json={}, headers=manager_headers).json()
        process_one()

        viewer_headers = login(client, "viewer@example.com")
        response = client.get(f"/api/v1/reports/runs/{run['id']}/download", headers=viewer_headers)
        assert response.status_code == 403
