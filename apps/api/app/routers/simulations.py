"""Monte Carlo simulations API (Milestones 6-7): configure a risk's
frequency-severity model and enqueue a run in one call, or trigger a
scenario's portfolio run, both dispatched to apps/worker via the JobQueue
(ADR 0005) since Monte Carlo iteration counts are too slow for a request
(see docs/architecture/01-target-architecture.md's async-boundaries table).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.deps import CurrentUser, get_current_user, get_db, require_permission
from packages.shared.models.jobs import BackgroundJob, JobStatus
from packages.shared.models.risk import Risk
from packages.shared.models.scenario import Scenario
from packages.shared.models.simulation import (
    SimulationConfig,
    SimulationResult,
    SimulationRun,
    SimulationRunStatus,
)
from packages.shared.rbac import (
    RUN_ANY_SIMULATION,
    RUN_OWN_SIMULATION,
    VIEW_SIMULATION_RESULTS,
    role_has_permission,
)
from packages.shared.schemas.simulation import (
    PortfolioSimulationRequest,
    SimulationConfigCreate,
    SimulationConfigOut,
    SimulationResultOut,
    SimulationRunOut,
)

router = APIRouter(prefix="/api/v1/simulations", tags=["simulations"])


def _can_run_for_risk(current_user: CurrentUser, risk: Risk) -> bool:
    if any(role_has_permission(r, RUN_ANY_SIMULATION) for r in current_user.roles):
        return True
    if any(role_has_permission(r, RUN_OWN_SIMULATION) for r in current_user.roles):
        return risk.owner_id == current_user.user.id
    return False


def _require_view(current_user: CurrentUser) -> None:
    if not any(role_has_permission(r, VIEW_SIMULATION_RESULTS) for r in current_user.roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="missing required permission: view_simulation_results",
        )


def _to_run_out(
    run: SimulationRun, result: SimulationResult | None, config: SimulationConfig | None
) -> SimulationRunOut:
    return SimulationRunOut(
        id=run.id,
        config_id=run.config_id,
        scenario_id=run.scenario_id,
        status=run.status,
        iterations_used=run.iterations_used,
        seed_used=run.seed_used,
        error=run.error,
        created_at=run.created_at,
        completed_at=run.completed_at,
        result=(
            SimulationResultOut(
                expected_annual_loss=float(result.expected_annual_loss),
                median=float(result.median),
                p75=float(result.p75),
                p90=float(result.p90),
                p95=float(result.p95),
                p99=float(result.p99),
                histogram=result.histogram,
                per_risk_contribution=result.per_risk_contribution,
            )
            if result
            else None
        ),
        config=SimulationConfigOut.model_validate(config) if config else None,
    )


def _enqueue_run(
    db: Session,
    *,
    config_id: uuid.UUID | None,
    scenario_id: uuid.UUID | None,
    iterations: int,
    seed: int,
    requested_by_id: uuid.UUID,
) -> SimulationRun:
    now = datetime.now(timezone.utc)
    run = SimulationRun(
        config_id=config_id,
        scenario_id=scenario_id,
        status=SimulationRunStatus.PENDING,
        iterations_used=iterations,
        seed_used=seed,
        requested_by_id=requested_by_id,
        created_at=now,
        updated_at=now,
    )
    db.add(run)
    db.flush()
    db.add(
        BackgroundJob(
            job_type="simulation_run",
            payload={"run_id": str(run.id)},
            status=JobStatus.PENDING,
            created_at=now,
            updated_at=now,
        )
    )
    db.commit()
    db.refresh(run)
    return run


@router.post("", response_model=SimulationRunOut, status_code=status.HTTP_202_ACCEPTED)
def create_config_and_run(
    payload: SimulationConfigCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    risk = db.get(Risk, payload.risk_id)
    if risk is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="risk not found")
    if not _can_run_for_risk(current_user, risk):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="cannot run simulations for this risk"
        )

    config = SimulationConfig(
        risk_id=payload.risk_id,
        distribution_type=payload.distribution_type,
        loss_min=payload.loss_min,
        loss_most_likely=payload.loss_most_likely,
        loss_max=payload.loss_max,
        annual_event_frequency=payload.annual_event_frequency,
        confidence=payload.confidence,
        correlation_group=payload.correlation_group,
        correlation_strength=payload.correlation_strength,
        iterations=payload.iterations,
        seed=payload.seed,
        created_by_id=current_user.user.id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(config)
    db.flush()

    run = _enqueue_run(
        db,
        config_id=config.id,
        scenario_id=None,
        iterations=config.iterations,
        seed=config.seed,
        requested_by_id=current_user.user.id,
    )
    return _to_run_out(run, None, config)


@router.get("", response_model=list[SimulationRunOut])
def list_runs(
    risk_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    _require_view(current_user)
    query = select(SimulationRun).order_by(SimulationRun.created_at.desc())
    if risk_id is not None:
        query = query.join(
            SimulationConfig, SimulationConfig.id == SimulationRun.config_id
        ).where(SimulationConfig.risk_id == risk_id)
    runs = db.scalars(query).all()

    results_by_run = {
        r.run_id: r
        for r in db.scalars(
            select(SimulationResult).where(SimulationResult.run_id.in_([run.id for run in runs]))
        ).all()
    }
    configs_by_id = {
        c.id: c
        for c in db.scalars(
            select(SimulationConfig).where(
                SimulationConfig.id.in_([run.config_id for run in runs if run.config_id])
            )
        ).all()
    }
    return [
        _to_run_out(run, results_by_run.get(run.id), configs_by_id.get(run.config_id))
        for run in runs
    ]


@router.post("/portfolio", response_model=SimulationRunOut, status_code=status.HTTP_202_ACCEPTED)
def run_portfolio_simulation_endpoint(
    payload: PortfolioSimulationRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(RUN_ANY_SIMULATION)),
):
    scenario = db.get(Scenario, payload.scenario_id)
    if scenario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="scenario not found")

    run = _enqueue_run(
        db,
        config_id=None,
        scenario_id=scenario.id,
        iterations=payload.iterations,
        seed=payload.seed,
        requested_by_id=current_user.user.id,
    )
    return _to_run_out(run, None, None)


@router.get("/{run_id}", response_model=SimulationRunOut)
def get_run(
    run_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    _require_view(current_user)
    run = db.get(SimulationRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="simulation run not found")
    result = db.scalars(select(SimulationResult).where(SimulationResult.run_id == run_id)).first()
    config = db.get(SimulationConfig, run.config_id) if run.config_id else None
    return _to_run_out(run, result, config)
