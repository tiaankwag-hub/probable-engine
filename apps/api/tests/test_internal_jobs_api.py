"""Internal-jobs router tests (Milestone 11). These endpoints carry no
app-level auth by design (see apps/api/app/routers/internal_jobs.py's
docstring) — their protection is Cloud Run ingress + IAM invoker, which
this test process can't simulate. What's tested here is that they're
reachable with zero auth headers (proving no accidental RBAC dependency
crept in) and that each does the one thing it's meant to do.
"""

from sqlalchemy import select

from packages.shared.models.jobs import BackgroundJob
from packages.shared.models.snapshot import Snapshot


class TestIngestEmergingSignals:
    def test_enqueues_a_pending_ingest_job_with_no_auth_header_at_all(self, client, db_session):
        response = client.post("/internal/jobs/ingest-emerging-signals")
        assert response.status_code == 202, response.text
        job_id = response.json()["job_id"]

        job = db_session.get(BackgroundJob, job_id)
        assert job.job_type == "emerging_signal_ingest"
        assert job.status.value == "pending"


class TestCaptureScheduledSnapshot:
    def test_creates_a_snapshot_with_no_auth_header_at_all(self, client, db_session, seeded):
        response = client.post("/internal/jobs/capture-snapshot")
        assert response.status_code == 201, response.text
        snapshot_id = response.json()["snapshot_id"]

        snapshot = db_session.get(Snapshot, snapshot_id)
        assert snapshot is not None
        assert "Scheduled snapshot" in snapshot.label

    def test_is_reachable_regardless_of_auth_mode(self, monkeypatch, tmp_path, seeded):
        """Cloud Scheduler never presents a bearer token or IAP assertion —
        this route must work the same whether the surrounding service is
        running in mock or iap auth_mode, since its own protection is a
        platform-level concern orthogonal to human auth_mode entirely."""
        from fastapi.testclient import TestClient

        from apps.api.app.deps import get_object_store
        from apps.api.app.main import create_app
        from packages.shared.storage import LocalFileSystemStore

        monkeypatch.setenv("AUTH_MODE", "iap")
        monkeypatch.setenv("IAP_AUDIENCE", "test-audience")
        app = create_app()
        app.dependency_overrides[get_object_store] = lambda: LocalFileSystemStore(
            tmp_path / "storage"
        )
        iap_mode_client = TestClient(app)

        response = iap_mode_client.post("/internal/jobs/ingest-emerging-signals")
        assert response.status_code == 202, response.text
