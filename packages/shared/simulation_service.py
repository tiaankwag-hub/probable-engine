"""Simulation orchestration (Milestones 6-7): converts between DB rows and
the pure `packages.simulations` engine, and persists results. The engine
itself has no database dependency at all — this module is the only place
that bridges the two, mirroring every other `*_service.py` in this
package. Callers (the worker job handlers) own the `SimulationRun`
status transitions and commit timing, the same split `report_generate.py`
uses against the equally-pure `packages.reporting` renderers.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.shared.models.scenario import ScenarioRisk
from packages.shared.models.simulation import SimulationConfig, SimulationResult, SimulationRun
from packages.simulations.engine import (
    RiskSimulationInput,
    SimulationParams,
    compute_statistics,
    run_annual_loss_simulation,
    run_portfolio_simulation,
)


class ScenarioHasNoLinkedRisksError(Exception):
    def __init__(self, scenario_id: uuid.UUID):
        self.scenario_id = scenario_id
        super().__init__(f"scenario {scenario_id} has no linked risks")


class RiskMissingSimulationConfigError(Exception):
    def __init__(self, risk_id: uuid.UUID):
        self.risk_id = risk_id
        super().__init__(f"risk {risk_id} has no simulation config yet")


def params_from_config(
    config: SimulationConfig, *, iterations: int | None = None, seed: int | None = None
) -> SimulationParams:
    return SimulationParams(
        distribution_type=config.distribution_type,
        loss_min=float(config.loss_min),
        loss_most_likely=float(config.loss_most_likely),
        loss_max=float(config.loss_max),
        annual_event_frequency=float(config.annual_event_frequency),
        iterations=iterations if iterations is not None else config.iterations,
        seed=seed if seed is not None else config.seed,
    )


def get_latest_config_for_risk(session: Session, risk_id: uuid.UUID) -> SimulationConfig | None:
    return session.scalars(
        select(SimulationConfig)
        .where(SimulationConfig.risk_id == risk_id)
        .order_by(SimulationConfig.created_at.desc())
    ).first()


def run_single_risk_simulation(session: Session, run: SimulationRun) -> SimulationResult:
    """Executes a single-risk run (`run.config_id` is set) and persists the
    `SimulationResult`. Caller commits."""
    config = session.get(SimulationConfig, run.config_id)
    if config is None:
        raise ValueError(f"simulation config not found: {run.config_id}")

    params = params_from_config(config, iterations=run.iterations_used, seed=run.seed_used)
    annual_losses = run_annual_loss_simulation(params)
    stats = compute_statistics(annual_losses)

    result = SimulationResult(
        run_id=run.id,
        expected_annual_loss=stats.expected_annual_loss,
        median=stats.median,
        p75=stats.p75,
        p90=stats.p90,
        p95=stats.p95,
        p99=stats.p99,
        histogram=stats.histogram,
        per_risk_contribution=None,
    )
    session.add(result)
    return result


def run_scenario_portfolio_simulation(session: Session, run: SimulationRun) -> SimulationResult:
    """Executes a portfolio run (`run.scenario_id` is set): looks up every
    risk linked to the scenario, requires each to already have its own
    `SimulationConfig` (raises rather than silently skipping an
    unconfigured risk — never presenting a partial portfolio as complete),
    correlates risks that share a `correlation_group`, and persists the
    portfolio-level `SimulationResult` plus each risk's tail-loss
    contribution. Caller commits.
    """
    scenario_risks = session.scalars(
        select(ScenarioRisk).where(ScenarioRisk.scenario_id == run.scenario_id)
    ).all()
    if not scenario_risks:
        raise ScenarioHasNoLinkedRisksError(str(run.scenario_id))

    risk_inputs = []
    for scenario_risk in scenario_risks:
        config = get_latest_config_for_risk(session, scenario_risk.risk_id)
        if config is None:
            raise RiskMissingSimulationConfigError(scenario_risk.risk_id)
        risk_inputs.append(
            RiskSimulationInput(
                risk_id=str(scenario_risk.risk_id),
                params=params_from_config(config),
                correlation_group=config.correlation_group,
                correlation_strength=(
                    float(config.correlation_strength)
                    if config.correlation_strength is not None
                    else None
                ),
            )
        )

    portfolio = run_portfolio_simulation(risk_inputs, iterations=run.iterations_used, seed=run.seed_used)
    stats = portfolio.portfolio_stats

    result = SimulationResult(
        run_id=run.id,
        expected_annual_loss=stats.expected_annual_loss,
        median=stats.median,
        p75=stats.p75,
        p90=stats.p90,
        p95=stats.p95,
        p99=stats.p99,
        histogram=stats.histogram,
        per_risk_contribution=portfolio.per_risk_contribution,
    )
    session.add(result)
    return result
