"""Direct unit tests of the simulation_service error paths that the DB's
own foreign-key constraints make unreachable through the normal API/worker
flow (e.g. simulation_runs.config_id cascades on delete, so a run can
never actually point at a missing config) but that the service still
guards against defensively. Constructs plain, unpersisted model instances
rather than inserting through the DB, so these don't need a live database.
"""

import os
import uuid

os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/risk_platform_test"
)

import pytest

from packages.shared.db import get_session_factory
from packages.shared.models.simulation import SimulationConfig, SimulationRun
from packages.shared.simulation_service import (
    RiskMissingSimulationConfigError,
    ScenarioHasNoLinkedRisksError,
    params_from_config,
)
from packages.simulations.distributions import DistributionType


class TestParamsFromConfig:
    def test_converts_decimal_fields_to_float(self):
        config = SimulationConfig(
            risk_id=uuid.uuid4(),
            distribution_type=DistributionType.PERT,
            loss_min=1000,
            loss_most_likely=5000,
            loss_max=20000,
            annual_event_frequency=1.5,
            iterations=1000,
            seed=42,
        )
        params = params_from_config(config)
        assert params.distribution_type == DistributionType.PERT
        assert params.loss_min == 1000.0
        assert params.iterations == 1000
        assert params.seed == 42

    def test_override_iterations_and_seed(self):
        config = SimulationConfig(
            risk_id=uuid.uuid4(),
            distribution_type=DistributionType.TRIANGULAR,
            loss_min=1,
            loss_most_likely=2,
            loss_max=3,
            annual_event_frequency=1.0,
            iterations=1000,
            seed=42,
        )
        params = params_from_config(config, iterations=50, seed=7)
        assert params.iterations == 50
        assert params.seed == 7


class TestErrorMessages:
    def test_scenario_has_no_linked_risks_error_message(self):
        scenario_id = uuid.uuid4()
        error = ScenarioHasNoLinkedRisksError(scenario_id)
        assert str(scenario_id) in str(error)
        assert "no linked risks" in str(error)

    def test_risk_missing_simulation_config_error_message(self):
        risk_id = uuid.uuid4()
        error = RiskMissingSimulationConfigError(risk_id)
        assert str(risk_id) in str(error)
        assert "no simulation config" in str(error)


class TestRunSingleRiskSimulationDefensiveCheck:
    def test_raises_when_config_id_points_nowhere(self):
        """simulation_runs.config_id cascades on delete, so this state is
        unreachable via the API/worker in practice — but the service
        checks for it anyway rather than crashing on a None attribute
        access, and that check deserves its own test."""
        from packages.shared.simulation_service import run_single_risk_simulation

        session = get_session_factory()()
        try:
            run = SimulationRun(
                id=uuid.uuid4(),
                config_id=uuid.uuid4(),
                scenario_id=None,
                iterations_used=10,
                seed_used=1,
                requested_by_id=uuid.uuid4(),
            )
            with pytest.raises(ValueError, match="simulation config not found"):
                run_single_risk_simulation(session, run)
        finally:
            session.close()
