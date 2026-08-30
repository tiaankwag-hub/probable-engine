from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select

from apps.worker.app.main import process_one
from database.seed.generate_fixture import _extend_rows
from packages.shared.importing.mapping import DEFAULT_RISK_REGISTER_MAPPING
from packages.shared.models.imports import ImportColumnMapping, ImportJob, ImportJobStatus
from packages.shared.models.jobs import BackgroundJob, JobStatus
from packages.shared.models.risk import Risk
from packages.shared.storage import LocalFileSystemStore

FIXTURE_PATH = (
    Path(__file__).parents[3] / "database" / "seed" / "fixtures" / "risk_register_fixture.xlsx"
)


def _seed_import_job(db_session, storage: LocalFileSystemStore, *, filename=FIXTURE_PATH):
    key = storage.put(filename, key="imports/test.xlsx")
    now = datetime.now(timezone.utc)
    job = ImportJob(
        filename=filename.name,
        storage_key=key,
        uploaded_by=None,
        status=ImportJobStatus.VALIDATED,
        created_at=now,
        updated_at=now,
    )
    db_session.add(job)
    db_session.flush()
    for spec in DEFAULT_RISK_REGISTER_MAPPING:
        db_session.add(
            ImportColumnMapping(
                import_job_id=job.id,
                source_column=spec.source_column,
                domain_field=spec.domain_field,
                transform=spec.transform,
            )
        )
    db_session.commit()
    return job


def _enqueue_commit_job(db_session, import_job_id):
    now = datetime.now(timezone.utc)
    background_job = BackgroundJob(
        job_type="import_commit",
        payload={"import_job_id": str(import_job_id), "actor_email": "worker-test@system"},
        status=JobStatus.PENDING,
        created_at=now,
        updated_at=now,
    )
    db_session.add(background_job)
    db_session.commit()
    db_session.refresh(background_job)
    return background_job


class TestWorkerProcessOne:
    def test_returns_false_when_queue_is_empty(self, db_session, seeded):
        assert process_one() is False

    def test_processes_import_commit_job_successfully(self, db_session, seeded, tmp_path, monkeypatch):
        monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
        storage = LocalFileSystemStore(tmp_path / "storage")

        import_job = _seed_import_job(db_session, storage)
        background_job = _enqueue_commit_job(db_session, import_job.id)

        processed = process_one()
        assert processed is True

        db_session.expire_all()
        refreshed_bg = db_session.get(BackgroundJob, background_job.id)
        assert refreshed_bg.status == JobStatus.SUCCEEDED
        assert refreshed_bg.error is None

        refreshed_job = db_session.get(ImportJob, import_job.id)
        assert refreshed_job.status == ImportJobStatus.COMMITTED

        risks = db_session.scalars(select(Risk)).all()
        assert len(risks) == 20
        assert {r.risk_code for r in risks} == {row["risk_id"] for row in _extend_rows()}

    def test_marks_job_failed_on_unknown_job_type(self, db_session, seeded, tmp_path, monkeypatch):
        monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
        now = datetime.now(timezone.utc)
        background_job = BackgroundJob(
            job_type="totally_unknown",
            payload={},
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
        assert "no handler registered" in refreshed.error

    def test_processes_oldest_job_first(self, db_session, seeded, tmp_path, monkeypatch):
        monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
        now = datetime.now(timezone.utc)
        earlier = now - timedelta(seconds=10)
        older = BackgroundJob(
            job_type="totally_unknown", payload={"marker": "older"},
            status=JobStatus.PENDING, created_at=earlier, updated_at=earlier,
        )
        db_session.add(older)
        db_session.commit()

        newer = BackgroundJob(
            job_type="totally_unknown", payload={"marker": "newer"},
            status=JobStatus.PENDING, created_at=now, updated_at=now,
        )
        db_session.add(newer)
        db_session.commit()

        process_one()
        db_session.expire_all()
        assert db_session.get(BackgroundJob, older.id).status == JobStatus.FAILED
        assert db_session.get(BackgroundJob, newer.id).status == JobStatus.PENDING
