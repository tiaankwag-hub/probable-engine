from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from apps.worker.app.main import process_one
from packages.shared.models.identity import User
from packages.shared.models.jobs import BackgroundJob, JobStatus
from packages.shared.models.scenario import Scenario, ScenarioRisk
from packages.shared.models.simulation import (
    SimulationConfig,
    SimulationResult,
    SimulationRun,
    SimulationRunStatus,
)
from packages.shared.risk_service import AssessmentInput, RiskFields, create_risk
from packages.simulations.distributions import DistributionType


def _make_risk(db_session, title="Worker sim risk"):
    fields = RiskFields(title=title)
    assessment = AssessmentInput(
        likelihood=3,
        impact_financial=3,
        impact_customer_service=3,
        impact_operational_delivery=3,
        impact_legal_regulatory=3,
        impact_reputation=3,
        impact_health_safety=3,
        control_effectiveness=3,
    )
    risk = create_risk(
        db_session,
        fields=fields,
        assessment_input=assessment,
        actor_email="worker-test@system",
        actor_id=None,
        source="test",
    )
    db_session.flush()
    return risk


def _make_config(db_session, risk, *, correlation_group=None, correlation_strength=None, seed=1):
    config = SimulationConfig(
        risk_id=risk.id,
        distribution_type=DistributionType.TRIANGULAR,
        loss_min=1000,
        loss_most_likely=10000,
        loss_max=100000,
        annual_event_frequency=2.0,
        correlation_group=correlation_group,
        correlation_strength=correlation_strength,
        iterations=300,
        seed=seed,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(config)
    db_session.flush()
    return config


def _enqueue_run(db_session, *, config_id=None, scenario_id=None, iterations=300, seed=1, requested_by):
    now = datetime.now(timezone.utc)
    run = SimulationRun(
        config_id=config_id,
        scenario_id=scenario_id,
        status=SimulationRunStatus.PENDING,
        iterations_used=iterations,
        seed_used=seed,
        requested_by_id=requested_by.id,
        created_at=now,
        updated_at=now,
    )
    db_session.add(run)
    db_session.flush()
    db_session.add(
        BackgroundJob(
            job_type="simulation_run",
            payload={"run_id": str(run.id)},
            status=JobStatus.PENDING,
            created_at=now,
            updated_at=now,
        )
    )
    db_session.commit()
    db_session.refresh(run)
    return run


class TestSingleRiskSimulationJob:
    def test_succeeds_and_persists_a_result(self, db_session, seeded):
        admin = db_session.scalars(select(User)).first()
        risk = _make_risk(db_session)
        config = _make_config(db_session, risk)
        run = _enqueue_run(db_session, config_id=config.id, requested_by=admin)

        assert process_one() is True

        db_session.expire_all()
        refreshed_run = db_session.get(SimulationRun, run.id)
        assert refreshed_run.status == SimulationRunStatus.SUCCEEDED
        assert refreshed_run.completed_at is not None

        result = db_session.scalars(
            select(SimulationResult).where(SimulationResult.run_id == run.id)
        ).first()
        assert result is not None
        assert result.p99 >= result.p95 >= result.p90
        assert len(result.histogram) > 0
        assert result.per_risk_contribution is None

class TestPortfolioSimulationJob:
    def test_correlated_portfolio_run_succeeds(self, db_session, seeded):
        admin = db_session.scalars(select(User)).first()
        risk_a = _make_risk(db_session, "Portfolio risk A")
        risk_b = _make_risk(db_session, "Portfolio risk B")
        _make_config(db_session, risk_a, correlation_group="cluster", correlation_strength=0.8, seed=1)
        _make_config(db_session, risk_b, correlation_group="cluster", correlation_strength=0.8, seed=2)

        scenario = Scenario(name="Correlated outage", created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
        db_session.add(scenario)
        db_session.flush()
        db_session.add(ScenarioRisk(scenario_id=scenario.id, risk_id=risk_a.id))
        db_session.add(ScenarioRisk(scenario_id=scenario.id, risk_id=risk_b.id))
        db_session.commit()

        run = _enqueue_run(db_session, scenario_id=scenario.id, iterations=400, seed=7, requested_by=admin)

        assert process_one() is True

        db_session.expire_all()
        refreshed_run = db_session.get(SimulationRun, run.id)
        assert refreshed_run.status == SimulationRunStatus.SUCCEEDED

        result = db_session.scalars(
            select(SimulationResult).where(SimulationResult.run_id == run.id)
        ).first()
        assert result.per_risk_contribution is not None
        assert set(result.per_risk_contribution.keys()) == {str(risk_a.id), str(risk_b.id)}
        assert abs(sum(result.per_risk_contribution.values()) - 1.0) < 1e-6

    def test_scenario_with_no_linked_risks_fails_the_run(self, db_session, seeded):
        admin = db_session.scalars(select(User)).first()
        scenario = Scenario(name="Empty scenario", created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
        db_session.add(scenario)
        db_session.commit()

        run = _enqueue_run(db_session, scenario_id=scenario.id, requested_by=admin)

        assert process_one() is True

        db_session.expire_all()
        refreshed_run = db_session.get(SimulationRun, run.id)
        assert refreshed_run.status == SimulationRunStatus.FAILED
        assert "no linked risks" in refreshed_run.error.lower()
