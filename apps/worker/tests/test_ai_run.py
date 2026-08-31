from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from apps.worker.app.main import process_one
from packages.shared.models.ai import AICapability, AIRun, AIRunStatus, AISuggestion
from packages.shared.models.control import Control, ControlAutomation, ControlType, RiskControl
from packages.shared.models.identity import User
from packages.shared.models.incident import Incident, IncidentSeverity
from packages.shared.models.jobs import BackgroundJob, JobStatus
from packages.shared.risk_service import AssessmentInput, RiskFields, create_risk


def _make_risk(db_session, title="Worker AI risk", likelihood=3, control_effectiveness=3):
    fields = RiskFields(title=title)
    assessment = AssessmentInput(
        likelihood=likelihood,
        impact_financial=3,
        impact_customer_service=3,
        impact_operational_delivery=3,
        impact_legal_regulatory=3,
        impact_reputation=3,
        impact_health_safety=3,
        control_effectiveness=control_effectiveness,
    )
    risk = create_risk(
        db_session, fields=fields, assessment_input=assessment,
        actor_email="worker-test@system", actor_id=None, source="test",
    )
    db_session.flush()
    return risk


def _enqueue_run(db_session, *, capability, requested_by, risk_id=None):
    now = datetime.now(timezone.utc)
    run = AIRun(
        capability=capability,
        prompt_version="v1",
        requested_by_id=requested_by.id,
        input_risk_ids=[str(risk_id)] if risk_id else [],
        sources={},
        status=AIRunStatus.PENDING,
        created_at=now,
        updated_at=now,
    )
    db_session.add(run)
    db_session.flush()

    payload = {"run_id": str(run.id)}
    if risk_id:
        payload["risk_id"] = str(risk_id)
    db_session.add(
        BackgroundJob(
            job_type="ai_run", payload=payload, status=JobStatus.PENDING, created_at=now, updated_at=now
        )
    )
    db_session.commit()
    db_session.refresh(run)
    return run


class TestExecutiveSummaryJob:
    def test_succeeds_using_mock_provider(self, db_session, seeded, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        admin = db_session.scalars(select(User)).first()
        _make_risk(db_session)
        db_session.commit()

        run = _enqueue_run(db_session, capability=AICapability.EXECUTIVE_SUMMARY, requested_by=admin)

        assert process_one() is True

        db_session.expire_all()
        refreshed = db_session.get(AIRun, run.id)
        assert refreshed.status == AIRunStatus.SUCCEEDED
        assert refreshed.model == "mock-analyst-v1"
        assert refreshed.raw_response
        assert refreshed.completed_at is not None


class TestRiskAnalysisJob:
    def test_succeeds_and_creates_no_suggestion_when_nothing_notable(self, db_session, seeded, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        admin = db_session.scalars(select(User)).first()
        risk = _make_risk(db_session, likelihood=2, control_effectiveness=4)
        db_session.commit()

        run = _enqueue_run(
            db_session, capability=AICapability.RISK_ANALYSIS, requested_by=admin, risk_id=risk.id
        )
        assert process_one() is True

        db_session.expire_all()
        refreshed = db_session.get(AIRun, run.id)
        assert refreshed.status == AIRunStatus.SUCCEEDED
        suggestions = db_session.scalars(select(AISuggestion).where(AISuggestion.run_id == run.id)).all()
        assert suggestions == []

    def test_recent_incident_produces_a_pending_suggestion(self, db_session, seeded, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        admin = db_session.scalars(select(User)).first()
        risk = _make_risk(db_session, likelihood=3, control_effectiveness=3)
        now = datetime.now(timezone.utc)
        db_session.add(
            Incident(
                incident_code="INC-TEST-0001",
                risk_id=risk.id,
                description="Test incident",
                incident_date=now.date(),
                severity=IncidentSeverity.HIGH,
                created_at=now,
                updated_at=now,
            )
        )
        db_session.commit()

        run = _enqueue_run(
            db_session, capability=AICapability.RISK_ANALYSIS, requested_by=admin, risk_id=risk.id
        )
        assert process_one() is True

        db_session.expire_all()
        suggestions = db_session.scalars(select(AISuggestion).where(AISuggestion.run_id == run.id)).all()
        assert len(suggestions) == 1
        suggestion = suggestions[0]
        assert suggestion.human_review_status == "pending"
        assert suggestion.proposed_changes == {"likelihood": 4}
        assert suggestion.risk_id == risk.id

    def test_missing_risk_fails_the_run(self, db_session, seeded, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        admin = db_session.scalars(select(User)).first()
        run = _enqueue_run(
            db_session, capability=AICapability.RISK_ANALYSIS, requested_by=admin, risk_id=uuid.uuid4()
        )

        assert process_one() is True

        db_session.expire_all()
        refreshed = db_session.get(AIRun, run.id)
        assert refreshed.status == AIRunStatus.FAILED
        assert "risk not found" in refreshed.error


def _link_control(db_session, risk, *, design_effectiveness, operating_effectiveness):
    control = Control(
        control_code=f"CTRL-TEST-{uuid.uuid4().hex[:8]}",
        name="Test control",
        control_type=ControlType.PREVENTIVE,
        automation=ControlAutomation.MANUAL,
        design_effectiveness=design_effectiveness,
        operating_effectiveness=operating_effectiveness,
    )
    db_session.add(control)
    db_session.flush()
    db_session.add(RiskControl(risk_id=risk.id, control_id=control.id))
    return control


class TestControlGapAnalysisJob:
    def test_no_linked_controls_produces_a_pending_new_control_suggestion(
        self, db_session, seeded, monkeypatch
    ):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        admin = db_session.scalars(select(User)).first()
        risk = _make_risk(db_session)
        db_session.commit()

        run = _enqueue_run(
            db_session, capability=AICapability.CONTROL_GAP_ANALYSIS, requested_by=admin, risk_id=risk.id
        )
        assert process_one() is True

        db_session.expire_all()
        refreshed = db_session.get(AIRun, run.id)
        assert refreshed.status == AIRunStatus.SUCCEEDED
        suggestions = db_session.scalars(select(AISuggestion).where(AISuggestion.run_id == run.id)).all()
        assert len(suggestions) == 1
        assert suggestions[0].suggestion_type == "new_control"
        assert suggestions[0].risk_id == risk.id

    def test_adequate_controls_produce_no_suggestion(self, db_session, seeded, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        admin = db_session.scalars(select(User)).first()
        risk = _make_risk(db_session)
        _link_control(db_session, risk, design_effectiveness=4, operating_effectiveness=4)
        db_session.commit()

        run = _enqueue_run(
            db_session, capability=AICapability.CONTROL_GAP_ANALYSIS, requested_by=admin, risk_id=risk.id
        )
        assert process_one() is True

        db_session.expire_all()
        suggestions = db_session.scalars(select(AISuggestion).where(AISuggestion.run_id == run.id)).all()
        assert suggestions == []

    def test_missing_risk_fails_the_run(self, db_session, seeded, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        admin = db_session.scalars(select(User)).first()
        run = _enqueue_run(
            db_session, capability=AICapability.CONTROL_GAP_ANALYSIS, requested_by=admin, risk_id=uuid.uuid4()
        )

        assert process_one() is True

        db_session.expire_all()
        refreshed = db_session.get(AIRun, run.id)
        assert refreshed.status == AIRunStatus.FAILED
        assert "risk not found" in refreshed.error


class TestEmergingRiskScanJob:
    def test_succeeds_using_mock_provider(self, db_session, seeded, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        admin = db_session.scalars(select(User)).first()
        _make_risk(db_session)
        db_session.commit()

        run = _enqueue_run(db_session, capability=AICapability.EMERGING_RISK_SCAN, requested_by=admin)
        assert process_one() is True

        db_session.expire_all()
        refreshed = db_session.get(AIRun, run.id)
        assert refreshed.status == AIRunStatus.SUCCEEDED
        assert refreshed.model == "mock-analyst-v1"


class TestMarketAnalysisJob:
    def test_succeeds_and_never_creates_a_suggestion(self, db_session, seeded, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        admin = db_session.scalars(select(User)).first()
        _make_risk(db_session)
        db_session.commit()

        run = _enqueue_run(db_session, capability=AICapability.MARKET_ANALYSIS, requested_by=admin)
        assert process_one() is True

        db_session.expire_all()
        refreshed = db_session.get(AIRun, run.id)
        assert refreshed.status == AIRunStatus.SUCCEEDED
        suggestions = db_session.scalars(select(AISuggestion).where(AISuggestion.run_id == run.id)).all()
        assert suggestions == []
