from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from apps.worker.app.main import process_one
from packages.shared.models.emerging_risk import EmergingRiskCandidate, EmergingSignal
from packages.shared.models.jobs import BackgroundJob, JobStatus
from packages.shared.models.risk import RiskCategory


def _enqueue_ingest(db_session):
    now = datetime.now(timezone.utc)
    job = BackgroundJob(
        job_type="emerging_signal_ingest", payload={}, status=JobStatus.PENDING,
        created_at=now, updated_at=now,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


class TestEmergingSignalIngestJob:
    def test_ingests_and_triages_against_known_categories(self, db_session, seeded, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        job = _enqueue_ingest(db_session)

        assert process_one() is True

        db_session.expire_all()
        refreshed = db_session.get(BackgroundJob, job.id)
        assert refreshed.status == JobStatus.SUCCEEDED

        signals = db_session.scalars(select(EmergingSignal)).all()
        assert len(signals) == 5
        candidates = db_session.scalars(select(EmergingRiskCandidate)).all()
        assert len(candidates) == 5
        assert all(c.lifecycle_status.value == "candidate" for c in candidates)
        assert all(c.model == "mock-analyst-v1" for c in candidates)

    def test_rerun_does_not_duplicate_signals(self, db_session, seeded, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        _enqueue_ingest(db_session)
        assert process_one() is True
        _enqueue_ingest(db_session)
        assert process_one() is True

        db_session.expire_all()
        assert len(db_session.scalars(select(EmergingSignal)).all()) == 5

    def test_no_known_categories_produces_signals_with_no_classification_and_no_candidates(
        self, db_session, monkeypatch
    ):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        # No `seeded` fixture here — no RiskCategory rows exist yet.
        assert db_session.scalar(select(RiskCategory)) is None
        _enqueue_ingest(db_session)

        assert process_one() is True

        db_session.expire_all()
        signals = db_session.scalars(select(EmergingSignal)).all()
        assert len(signals) == 5
        assert all(s.classification is None for s in signals)
        assert db_session.scalar(select(EmergingRiskCandidate)) is None
