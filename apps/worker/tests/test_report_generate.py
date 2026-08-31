from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from apps.worker.app.main import process_one
from packages.shared.models.identity import User
from packages.shared.models.jobs import BackgroundJob, JobStatus
from packages.shared.models.report import ReportRun, ReportRunStatus, ReportType


def _enqueue_report_run(db_session, *, report_type=ReportType.PDF_EXECUTIVE_SUMMARY, requested_by):
    now = datetime.now(timezone.utc)
    run = ReportRun(
        report_type=report_type,
        requested_by_id=requested_by.id,
        scope={},
        status=ReportRunStatus.PENDING,
        created_at=now,
        updated_at=now,
    )
    db_session.add(run)
    db_session.flush()

    background_job = BackgroundJob(
        job_type="report_generate",
        payload={"report_run_id": str(run.id)},
        status=JobStatus.PENDING,
        created_at=now,
        updated_at=now,
    )
    db_session.add(background_job)
    db_session.commit()
    db_session.refresh(run)
    db_session.refresh(background_job)
    return run, background_job


class TestReportGenerateJob:
    def test_generates_pdf_and_marks_run_succeeded(self, db_session, seeded, tmp_path, monkeypatch):
        monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
        admin = db_session.scalars(select(User)).first()
        run, background_job = _enqueue_report_run(db_session, requested_by=admin)

        processed = process_one()
        assert processed is True

        db_session.expire_all()
        refreshed_bg = db_session.get(BackgroundJob, background_job.id)
        assert refreshed_bg.status == JobStatus.SUCCEEDED

        refreshed_run = db_session.get(ReportRun, run.id)
        assert refreshed_run.status == ReportRunStatus.SUCCEEDED
        assert refreshed_run.generated_file_key is not None
        assert refreshed_run.generated_at is not None

        stored_path = tmp_path / "storage" / refreshed_run.generated_file_key
        assert stored_path.exists()
        assert stored_path.read_bytes().startswith(b"%PDF")

    def test_generates_pptx_two_slide_elt(self, db_session, seeded, tmp_path, monkeypatch):
        monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
        admin = db_session.scalars(select(User)).first()
        run, _ = _enqueue_report_run(
            db_session, report_type=ReportType.PPTX_TWO_SLIDE_ELT, requested_by=admin
        )

        process_one()

        db_session.expire_all()
        refreshed_run = db_session.get(ReportRun, run.id)
        assert refreshed_run.status == ReportRunStatus.SUCCEEDED

        stored_path = tmp_path / "storage" / refreshed_run.generated_file_key
        assert stored_path.suffix == ".pptx"
        assert stored_path.exists()

    def test_marks_run_failed_when_report_run_missing(self, db_session, seeded, tmp_path, monkeypatch):
        monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
        now = datetime.now(timezone.utc)
        background_job = BackgroundJob(
            job_type="report_generate",
            payload={"report_run_id": "00000000-0000-0000-0000-000000000000"},
            status=JobStatus.PENDING,
            created_at=now,
            updated_at=now,
        )
        db_session.add(background_job)
        db_session.commit()

        processed = process_one()
        assert processed is True

        db_session.expire_all()
        refreshed = db_session.get(BackgroundJob, background_job.id)
        assert refreshed.status == JobStatus.FAILED
        assert "report run not found" in refreshed.error
