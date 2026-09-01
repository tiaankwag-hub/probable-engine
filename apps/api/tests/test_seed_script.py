"""Regression test for a real bug: a database seeded by the Milestone 1/2
version of seed.py already has the 20 demo risks. Milestone 3 added
controls/actions seeding, but nested it inside a function that bailed out
entirely once any risk existed — so upgrading and re-running seed.py left
the new tables empty, invisible until a live check on a persisted database
surfaced it. seed_demo_risks must backfill controls/actions for
already-existing risks, not just on a fully empty database.
"""

from sqlalchemy import select

from database.seed.seed import (
    seed_demo_ai_content,
    seed_demo_emerging_risk_content,
    seed_demo_issues_and_incidents,
    seed_demo_risk_intake_content,
    seed_demo_risks,
    seed_demo_simulations,
)
from packages.shared.models.action import Action
from packages.shared.models.ai import AIRun, AISuggestion
from packages.shared.models.control import Control, RiskControl
from packages.shared.models.emerging_risk import CandidateLifecycleStatus, EmergingRiskCandidate, EmergingSignal
from packages.shared.models.risk import Risk
from packages.shared.models.risk_intake import IntakeSessionStatus, RiskIntakeSession
from packages.shared.models.scenario import Scenario, ScenarioRisk
from packages.shared.models.simulation import SimulationConfig, SimulationResult, SimulationRun


class TestSeedBackfill:
    def test_first_run_creates_risks_controls_and_actions(self, db_session, seeded):
        created = seed_demo_risks(db_session)
        db_session.commit()

        assert created == 20
        assert db_session.scalar(select(Risk).limit(1)) is not None
        assert len(db_session.scalars(select(Control)).all()) == 6
        assert len(db_session.scalars(select(Action)).all()) == 20

    def test_rerun_against_risks_that_already_exist_backfills_controls_and_actions(
        self, db_session, seeded
    ):
        """Simulates exactly what happened on a database carried over from
        Milestone 1/2: risks exist, controls/actions tables are empty."""
        first_pass_created = seed_demo_risks(db_session)
        db_session.commit()
        assert first_pass_created == 20

        # Wipe controls/actions only, as if this were a pre-Milestone-3 database.
        db_session.query(RiskControl).delete()
        db_session.query(Control).delete()
        db_session.query(Action).delete()
        db_session.commit()

        second_pass_created = seed_demo_risks(db_session)
        db_session.commit()

        assert second_pass_created == 0, "must not create duplicate risks"
        assert len(db_session.scalars(select(Control)).all()) == 6
        assert len(db_session.scalars(select(Action)).all()) == 20
        assert len(db_session.scalars(select(RiskControl)).all()) > 0

    def test_rerun_is_fully_idempotent_when_everything_already_seeded(self, db_session, seeded):
        seed_demo_risks(db_session)
        db_session.commit()

        seed_demo_risks(db_session)
        db_session.commit()

        assert len(db_session.scalars(select(Risk)).all()) == 20
        assert len(db_session.scalars(select(Control)).all()) == 6
        assert len(db_session.scalars(select(Action)).all()) == 20


class TestSeedDemoSimulations:
    def test_creates_configs_completed_runs_and_a_correlated_scenario(self, db_session, seeded):
        seed_demo_risks(db_session)
        db_session.commit()

        created = seed_demo_simulations(db_session)
        db_session.commit()

        assert created is True
        configs = db_session.scalars(select(SimulationConfig)).all()
        assert len(configs) == 3

        runs = db_session.scalars(select(SimulationRun)).all()
        assert len(runs) == 4  # 3 single-risk + 1 portfolio
        assert all(r.status == "succeeded" for r in runs)

        results = db_session.scalars(select(SimulationResult)).all()
        assert len(results) == 4
        assert all(r.expected_annual_loss >= 0 for r in results)

        scenario = db_session.scalars(select(Scenario)).first()
        assert scenario is not None
        assert len(db_session.scalars(select(ScenarioRisk)).all()) == 2

        portfolio_result = db_session.scalars(
            select(SimulationResult).join(SimulationRun).where(SimulationRun.scenario_id == scenario.id)
        ).first()
        assert portfolio_result.per_risk_contribution is not None
        assert abs(sum(portfolio_result.per_risk_contribution.values()) - 1.0) < 1e-6

    def test_is_idempotent_on_rerun(self, db_session, seeded):
        seed_demo_risks(db_session)
        db_session.commit()

        first = seed_demo_simulations(db_session)
        db_session.commit()
        second = seed_demo_simulations(db_session)
        db_session.commit()

        assert first is True
        assert second is False
        assert len(db_session.scalars(select(SimulationConfig)).all()) == 3
        assert len(db_session.scalars(select(Scenario)).all()) == 1

    def test_skips_when_risks_do_not_exist_yet(self, db_session, seeded):
        created = seed_demo_simulations(db_session)
        db_session.commit()

        assert created is False
        assert db_session.scalar(select(SimulationConfig)) is None


class TestSeedDemoAiContent:
    def test_creates_one_run_per_capability_with_genuine_suggestions(
        self, db_session, seeded, monkeypatch
    ):
        """5 capabilities seeded (executive summary, risk analysis,
        control-gap analysis, emerging-risk scan, market analysis); 3 of
        them produce a suggestion because the underlying facts genuinely
        warrant one (RSK-1002's incident, RSK-1004's weak control, and the
        least-covered category), not because the mock fabricates one."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        seed_demo_risks(db_session)
        db_session.commit()
        seed_demo_issues_and_incidents(db_session)
        db_session.commit()

        created = seed_demo_ai_content(db_session)
        db_session.commit()

        assert created is True
        runs = db_session.scalars(select(AIRun)).all()
        assert len(runs) == 5
        assert all(r.status == "succeeded" for r in runs)
        assert all(r.model == "mock-analyst-v1" for r in runs)

        suggestions = db_session.scalars(select(AISuggestion)).all()
        assert len(suggestions) == 3
        assert all(s.human_review_status == "pending" for s in suggestions)
        suggestion_types = {s.suggestion_type for s in suggestions}
        assert suggestion_types == {"assessment_change", "new_control", "new_risk"}
        # the new_risk suggestion (from the emerging-risk scan) has no existing risk yet
        assert any(s.risk_id is None for s in suggestions)

    def test_is_idempotent_on_rerun(self, db_session, seeded, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        seed_demo_risks(db_session)
        db_session.commit()
        seed_demo_issues_and_incidents(db_session)
        db_session.commit()

        first = seed_demo_ai_content(db_session)
        db_session.commit()
        second = seed_demo_ai_content(db_session)
        db_session.commit()

        assert first is True
        assert second is False
        assert len(db_session.scalars(select(AIRun)).all()) == 5

    def test_skips_when_target_risk_does_not_exist_yet(self, db_session, seeded, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        created = seed_demo_ai_content(db_session)
        db_session.commit()

        assert created is False
        assert db_session.scalar(select(AIRun)) is None


class TestSeedDemoEmergingRiskContent:
    def test_ingests_signals_and_demonstrates_the_full_lifecycle(self, db_session, seeded, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        created = seed_demo_emerging_risk_content(db_session)
        db_session.commit()

        assert created is True
        signals = db_session.scalars(select(EmergingSignal)).all()
        assert len(signals) == 5
        assert all(s.classification is not None for s in signals)

        candidates = db_session.scalars(
            select(EmergingRiskCandidate).order_by(EmergingRiskCandidate.created_at)
        ).all()
        assert len(candidates) == 5

        statuses = [c.lifecycle_status for c in candidates]
        assert statuses[0] == CandidateLifecycleStatus.ACCEPTED
        assert candidates[0].created_risk_id is not None
        assert statuses[1] == CandidateLifecycleStatus.DISMISSED
        assert statuses[2] == CandidateLifecycleStatus.UNDER_REVIEW
        assert statuses[3] == CandidateLifecycleStatus.CANDIDATE
        assert statuses[4] == CandidateLifecycleStatus.CANDIDATE

    def test_is_idempotent_on_rerun(self, db_session, seeded, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        first = seed_demo_emerging_risk_content(db_session)
        db_session.commit()
        second = seed_demo_emerging_risk_content(db_session)
        db_session.commit()

        assert first is True
        assert second is False
        assert len(db_session.scalars(select(EmergingSignal)).all()) == 5
        assert len(db_session.scalars(select(EmergingRiskCandidate)).all()) == 5

    def test_skips_when_no_users_are_seeded_yet(self, db_session):
        created = seed_demo_emerging_risk_content(db_session)
        db_session.commit()

        assert created is False


class TestSeedDemoRiskIntakeContent:
    def test_walks_a_full_conversation_to_a_submitted_draft_risk(self, db_session, seeded):
        created = seed_demo_risk_intake_content(db_session)
        db_session.commit()

        assert created is True
        sessions = db_session.scalars(select(RiskIntakeSession)).all()
        assert len(sessions) == 1
        intake = sessions[0]
        assert intake.status == IntakeSessionStatus.SUBMITTED
        assert intake.resulting_risk_id is not None
        assert intake.draft_fields["title"] == "Loading dock access control failure"

        risk = db_session.get(Risk, intake.resulting_risk_id)
        assert risk.status.value == "draft"
        assert risk.likelihood == 1

    def test_is_idempotent_on_rerun(self, db_session, seeded):
        first = seed_demo_risk_intake_content(db_session)
        db_session.commit()
        second = seed_demo_risk_intake_content(db_session)
        db_session.commit()

        assert first is True
        assert second is False
        assert len(db_session.scalars(select(RiskIntakeSession)).all()) == 1

    def test_skips_when_no_users_are_seeded_yet(self, db_session):
        created = seed_demo_risk_intake_content(db_session)
        db_session.commit()

        assert created is False
        assert db_session.scalar(select(EmergingSignal)) is None
