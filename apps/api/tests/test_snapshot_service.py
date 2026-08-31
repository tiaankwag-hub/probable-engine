from datetime import date

from database.seed.seed import seed_categories, seed_roles, seed_scoring_config, seed_users
from packages.shared.import_service import find_owner, get_or_create_category, row_to_inputs
from packages.shared.models.risk import Risk, RiskStatus
from packages.shared.risk_service import create_risk
from packages.shared.snapshot_service import capture_snapshot, compute_trend, compute_what_changed


def _make_risk(session, *, title, financial=3, likelihood=3, control_effectiveness=3):
    from packages.risk_engine.scoring import ImpactScores
    from packages.shared.risk_service import AssessmentInput, RiskFields

    fields = RiskFields(title=title)
    assessment = AssessmentInput(
        likelihood=likelihood,
        impact_financial=financial, impact_customer_service=financial,
        impact_operational_delivery=financial, impact_legal_regulatory=financial,
        impact_reputation=financial, impact_health_safety=financial,
        control_effectiveness=control_effectiveness,
    )
    return create_risk(
        session, fields=fields, assessment_input=assessment,
        actor_email="test@system", actor_id=None, source="test",
    )


class TestCaptureAndWhatChanged:
    def test_capture_snapshot_freezes_current_risks(self, db_session, seeded):
        risk = _make_risk(db_session, title="Snapshot test risk")
        db_session.commit()

        snapshot = capture_snapshot(
            db_session, label="Test period", period_end=date.today(), actor_email="test@system"
        )
        db_session.commit()

        assert snapshot.label == "Test period"
        assert len(snapshot.snapshot_risks) == 1
        assert snapshot.snapshot_risks[0].frozen_state["risk_code"] == risk.risk_code

    def test_new_risk_detected(self, db_session, seeded):
        _make_risk(db_session, title="Existed before")
        db_session.commit()
        snapshot = capture_snapshot(
            db_session, label="Before", period_end=date.today(), actor_email="t"
        )
        db_session.commit()

        _make_risk(db_session, title="New risk since snapshot")
        db_session.commit()

        result = compute_what_changed(db_session, snapshot.id)
        new_titles = [r["title"] for r in result["new_risks"]]
        assert "New risk since snapshot" in new_titles
        assert "Existed before" not in new_titles

    def test_closed_risk_detected(self, db_session, seeded):
        risk = _make_risk(db_session, title="Will be closed")
        db_session.commit()
        snapshot = capture_snapshot(
            db_session, label="Before", period_end=date.today(), actor_email="t"
        )
        db_session.commit()

        risk = db_session.get(Risk, risk.id)
        risk.status = RiskStatus.CLOSED
        db_session.commit()

        result = compute_what_changed(db_session, snapshot.id)
        closed_titles = [r["title"] for r in result["closed_risks"]]
        assert "Will be closed" in closed_titles

    def test_escalated_and_downgraded_risks_detected(self, db_session, seeded):
        low_risk = _make_risk(db_session, title="Will escalate", financial=1, likelihood=1)
        high_risk = _make_risk(db_session, title="Will downgrade", financial=5, likelihood=5, control_effectiveness=None)
        db_session.commit()
        snapshot = capture_snapshot(
            db_session, label="Before", period_end=date.today(), actor_email="t"
        )
        db_session.commit()

        from packages.shared.risk_service import AssessmentInput, update_risk

        low_risk = db_session.get(Risk, low_risk.id)
        update_risk(
            db_session, risk=low_risk, expected_version=low_risk.version, field_updates={},
            assessment_input=AssessmentInput(
                likelihood=5, impact_financial=5, impact_customer_service=5,
                impact_operational_delivery=5, impact_legal_regulatory=5,
                impact_reputation=5, impact_health_safety=5, control_effectiveness=None,
            ),
            actor_email="t", actor_id=None, source="test",
        )
        high_risk = db_session.get(Risk, high_risk.id)
        update_risk(
            db_session, risk=high_risk, expected_version=high_risk.version, field_updates={},
            assessment_input=AssessmentInput(
                likelihood=1, impact_financial=1, impact_customer_service=1,
                impact_operational_delivery=1, impact_legal_regulatory=1,
                impact_reputation=1, impact_health_safety=1, control_effectiveness=5,
            ),
            actor_email="t", actor_id=None, source="test",
        )
        db_session.commit()

        result = compute_what_changed(db_session, snapshot.id)
        escalated_titles = [r["title"] for r in result["escalated_risks"]]
        downgraded_titles = [r["title"] for r in result["downgraded_risks"]]
        assert "Will escalate" in escalated_titles
        assert "Will downgrade" in downgraded_titles

    def test_owner_change_detected(self, db_session, seeded):
        from sqlalchemy import select

        from packages.shared.models.identity import User
        from packages.shared.risk_service import update_risk

        risk = _make_risk(db_session, title="Ownership changes")
        db_session.commit()
        snapshot = capture_snapshot(
            db_session, label="Before", period_end=date.today(), actor_email="t"
        )
        db_session.commit()

        new_owner = db_session.scalars(select(User).limit(1)).first()
        risk = db_session.get(Risk, risk.id)
        update_risk(
            db_session, risk=risk, expected_version=risk.version,
            field_updates={"owner_id": new_owner.id}, assessment_input=None,
            actor_email="t", actor_id=None, source="test",
        )
        db_session.commit()

        result = compute_what_changed(db_session, snapshot.id)
        owner_change_titles = [r["title"] for r in result["owner_changes"]]
        assert "Ownership changes" in owner_change_titles

    def test_unknown_snapshot_raises(self, db_session, seeded):
        import uuid

        import pytest

        with pytest.raises(ValueError):
            compute_what_changed(db_session, uuid.uuid4())


class TestTrend:
    def test_trend_includes_snapshot_and_current_points(self, db_session, seeded):
        _make_risk(db_session, title="Trend risk")
        db_session.commit()
        capture_snapshot(db_session, label="Month 1", period_end=date(2026, 1, 1), actor_email="t")
        db_session.commit()

        points = compute_trend(db_session)
        labels = [p["label"] for p in points]
        assert "Month 1" in labels
        assert "Current" in labels
        assert points[-1]["label"] == "Current"

    def test_trend_excludes_closed_risks_from_counts(self, db_session, seeded):
        risk = _make_risk(db_session, title="Closed for trend")
        db_session.commit()
        capture_snapshot(db_session, label="Before close", period_end=date.today(), actor_email="t")
        db_session.commit()

        risk = db_session.get(Risk, risk.id)
        risk.status = RiskStatus.CLOSED
        db_session.commit()

        points = compute_trend(db_session)
        current_point = next(p for p in points if p["label"] == "Current")
        assert current_point["total_risks"] == 0
