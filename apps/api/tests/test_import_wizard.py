from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import Workbook
from sqlalchemy import select

from apps.api.app.deps import get_object_store
from apps.api.app.main import app
from apps.api.tests.conftest import login
from database.seed.generate_fixture import COLUMNS as FIXTURE_COLUMNS
from database.seed.generate_fixture import _extend_rows
from packages.shared.import_service import ImportHasBlockingErrors, commit_import_job
from packages.shared.models.imports import ImportJob, ImportJobStatus
from packages.shared.models.risk import Risk

FIXTURE_PATH = Path(__file__).parents[3] / "database" / "seed" / "fixtures" / "risk_register_fixture.xlsx"


def upload_fixture(client, headers, path=FIXTURE_PATH):
    with open(path, "rb") as f:
        response = client.post(
            "/api/v1/imports",
            files={"file": (path.name, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=headers,
        )
    assert response.status_code == 201, response.text
    return response.json()


def apply_suggested_mapping(client, headers, job_id):
    columns_response = client.get(f"/api/v1/imports/{job_id}/columns", headers=headers)
    assert columns_response.status_code == 200
    suggested = columns_response.json()["suggested_mapping"]
    mapping_response = client.put(
        f"/api/v1/imports/{job_id}/mapping", json={"mappings": suggested}, headers=headers
    )
    assert mapping_response.status_code == 200
    return columns_response.json()


class TestImportWizardHappyPath:
    def test_upload_requires_run_imports_permission(self, client):
        headers = login(client, "viewer@example.com")
        with open(FIXTURE_PATH, "rb") as f:
            response = client.post(
                "/api/v1/imports",
                files={"file": (FIXTURE_PATH.name, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                headers=headers,
            )
        assert response.status_code == 403

    def test_columns_endpoint_returns_all_36_columns(self, client):
        headers = login(client, "risk.manager@example.com")
        job = upload_fixture(client, headers)
        result = apply_suggested_mapping(client, headers, job["id"])
        assert result["columns"] == FIXTURE_COLUMNS
        assert len(result["columns"]) == 36
        assert all(entry["domain_field"] for entry in result["suggested_mapping"] if entry["source_column"] != "risk_statement_cause_event_impact")

    def test_validate_fixture_has_no_blocking_errors(self, client):
        headers = login(client, "risk.manager@example.com")
        job = upload_fixture(client, headers)
        apply_suggested_mapping(client, headers, job["id"])
        response = client.post(f"/api/v1/imports/{job['id']}/validate", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["blocking_error_count"] == 0

    def test_preview_returns_all_rows(self, client):
        headers = login(client, "risk.manager@example.com")
        job = upload_fixture(client, headers)
        apply_suggested_mapping(client, headers, job["id"])
        client.post(f"/api/v1/imports/{job['id']}/validate", headers=headers)
        response = client.get(f"/api/v1/imports/{job['id']}/preview", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["total_rows"] == 20
        assert body["rows"][0]["mapped"]["risk_code"] == "RSK-1001"

    def test_commit_endpoint_returns_202_and_enqueues_job(self, client):
        headers = login(client, "risk.manager@example.com")
        job = upload_fixture(client, headers)
        apply_suggested_mapping(client, headers, job["id"])
        client.post(f"/api/v1/imports/{job['id']}/validate", headers=headers)
        response = client.post(f"/api/v1/imports/{job['id']}/commit", headers=headers)
        assert response.status_code == 202
        assert response.json()["status"] == "pending"

    def test_worker_commit_creates_risks_and_marks_job_committed(self, client, db_session):
        headers = login(client, "risk.manager@example.com")
        job = upload_fixture(client, headers)
        apply_suggested_mapping(client, headers, job["id"])
        client.post(f"/api/v1/imports/{job['id']}/validate", headers=headers)
        client.post(f"/api/v1/imports/{job['id']}/commit", headers=headers)

        store = app.dependency_overrides[get_object_store]()
        summary = commit_import_job(
            db_session, import_job_id=job["id"], object_store=store, actor_email="worker@system"
        )
        db_session.commit()

        assert summary.created == 20
        risks = db_session.scalars(select(Risk)).all()
        assert len(risks) == 20
        assert {r.risk_code for r in risks} == {row["risk_id"] for row in _extend_rows()}

        refreshed_job = db_session.get(ImportJob, job["id"])
        assert refreshed_job.status == ImportJobStatus.COMMITTED

    def test_reimporting_same_fixture_never_overwrites_existing_risks(self, client, db_session):
        headers = login(client, "risk.manager@example.com")
        store = app.dependency_overrides[get_object_store]()

        job1 = upload_fixture(client, headers)
        apply_suggested_mapping(client, headers, job1["id"])
        client.post(f"/api/v1/imports/{job1['id']}/validate", headers=headers)
        client.post(f"/api/v1/imports/{job1['id']}/commit", headers=headers)
        commit_import_job(
            db_session, import_job_id=job1["id"], object_store=store, actor_email="worker@system"
        )
        db_session.commit()

        original_titles = {r.risk_code: r.title for r in db_session.scalars(select(Risk)).all()}

        job2 = upload_fixture(client, headers)
        apply_suggested_mapping(client, headers, job2["id"])
        client.post(f"/api/v1/imports/{job2['id']}/validate", headers=headers)
        client.post(f"/api/v1/imports/{job2['id']}/commit", headers=headers)
        summary2 = commit_import_job(
            db_session, import_job_id=job2["id"], object_store=store, actor_email="worker@system"
        )
        db_session.commit()

        assert summary2.created == 0
        assert summary2.skipped_existing_risk_code == 20
        risks = db_session.scalars(select(Risk)).all()
        assert len(risks) == 20
        for risk in risks:
            assert risk.title == original_titles[risk.risk_code]


class TestImportWizardValidationIssues:
    def _upload_bad_file(self, client, headers, tmp_path):
        wb = Workbook()
        ws = wb.active
        ws.append(["risk_id", "risk_title", "financial_impact_1_5", "likelihood_1_5_12_month_horizon"])
        ws.append(["RSK-BAD-1", "Bad row", 99, 3])  # invalid impact score
        path = tmp_path / "bad.xlsx"
        wb.save(path)
        return upload_fixture(client, headers, path=path)

    def test_invalid_impact_score_blocks_commit(self, client, db_session, tmp_path):
        headers = login(client, "risk.manager@example.com")
        job = self._upload_bad_file(client, headers, tmp_path)

        mapping = [
            {"source_column": "risk_id", "domain_field": "risk_code", "transform": "strip_text"},
            {"source_column": "risk_title", "domain_field": "title", "transform": "strip_text"},
            {"source_column": "financial_impact_1_5", "domain_field": "impact_financial", "transform": "parse_int_1_to_5"},
            {"source_column": "likelihood_1_5_12_month_horizon", "domain_field": "likelihood", "transform": "parse_int_1_to_5"},
        ]
        client.put(f"/api/v1/imports/{job['id']}/mapping", json={"mappings": mapping}, headers=headers)
        validate_response = client.post(f"/api/v1/imports/{job['id']}/validate", headers=headers)
        assert validate_response.json()["blocking_error_count"] > 0

        client.post(f"/api/v1/imports/{job['id']}/commit", headers=headers)
        store = app.dependency_overrides[get_object_store]()

        with pytest.raises(ImportHasBlockingErrors):
            commit_import_job(
                db_session, import_job_id=job["id"], object_store=store, actor_email="worker@system"
            )
        db_session.commit()
        refreshed = db_session.get(ImportJob, job["id"])
        assert refreshed.status == ImportJobStatus.FAILED
        assert db_session.scalars(select(Risk)).all() == []
