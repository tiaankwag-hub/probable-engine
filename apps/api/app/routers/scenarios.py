"""Scenario analysis API (Milestone 7): named what-if narratives linking
one or more risks, used as the target of a portfolio Monte Carlo run
(see simulations.py's `/simulations/portfolio`).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.deps import CurrentUser, get_db, require_permission
from packages.shared.models.risk import Risk
from packages.shared.models.scenario import Scenario, ScenarioRisk
from packages.shared.models.simulation import SimulationRun
from packages.shared.rbac import MANAGE_SCENARIOS, VIEW_RISKS
from packages.shared.schemas.scenario import (
    ScenarioCreate,
    ScenarioExposureOut,
    ScenarioOut,
    ScenarioUpdate,
)
from packages.shared.simulation_service import get_latest_config_for_risk

router = APIRouter(prefix="/api/v1/scenarios", tags=["scenarios"])


def _get_scenario_or_404(db: Session, scenario_id: uuid.UUID) -> Scenario:
    scenario = db.get(Scenario, scenario_id)
    if scenario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="scenario not found")
    return scenario


def _linked_risk_ids(db: Session, scenario_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        db.scalars(select(ScenarioRisk.risk_id).where(ScenarioRisk.scenario_id == scenario_id)).all()
    )


def _to_out(db: Session, scenario: Scenario) -> ScenarioOut:
    return ScenarioOut(
        id=scenario.id,
        name=scenario.name,
        description=scenario.description,
        assumptions=scenario.assumptions,
        duration_days=scenario.duration_days,
        financial_impact_min=(
            float(scenario.financial_impact_min) if scenario.financial_impact_min is not None else None
        ),
        financial_impact_most_likely=(
            float(scenario.financial_impact_most_likely)
            if scenario.financial_impact_most_likely is not None
            else None
        ),
        financial_impact_max=(
            float(scenario.financial_impact_max) if scenario.financial_impact_max is not None else None
        ),
        operational_impact=scenario.operational_impact,
        recovery_assumptions=scenario.recovery_assumptions,
        created_at=scenario.created_at,
        updated_at=scenario.updated_at,
        linked_risk_ids=_linked_risk_ids(db, scenario.id),
    )


@router.get("", response_model=list[ScenarioOut])
def list_scenarios(
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(VIEW_RISKS)),
):
    scenarios = db.scalars(select(Scenario).order_by(Scenario.created_at.desc())).all()
    return [_to_out(db, s) for s in scenarios]


@router.post("", response_model=ScenarioOut, status_code=status.HTTP_201_CREATED)
def create_scenario(
    payload: ScenarioCreate,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(MANAGE_SCENARIOS)),
):
    now = datetime.now(timezone.utc)
    scenario = Scenario(**payload.model_dump(), created_at=now, updated_at=now)
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return _to_out(db, scenario)


@router.get("/{scenario_id}", response_model=ScenarioOut)
def get_scenario(
    scenario_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(VIEW_RISKS)),
):
    scenario = _get_scenario_or_404(db, scenario_id)
    return _to_out(db, scenario)


@router.patch("/{scenario_id}", response_model=ScenarioOut)
def update_scenario(
    scenario_id: uuid.UUID,
    payload: ScenarioUpdate,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(MANAGE_SCENARIOS)),
):
    scenario = _get_scenario_or_404(db, scenario_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(scenario, field, value)
    scenario.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(scenario)
    return _to_out(db, scenario)


@router.post("/{scenario_id}/risks", response_model=ScenarioOut, status_code=status.HTTP_201_CREATED)
def link_risk(
    scenario_id: uuid.UUID,
    risk_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(MANAGE_SCENARIOS)),
):
    scenario = _get_scenario_or_404(db, scenario_id)
    if db.get(Risk, risk_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="risk not found")

    existing = db.scalars(
        select(ScenarioRisk).where(
            ScenarioRisk.scenario_id == scenario_id, ScenarioRisk.risk_id == risk_id
        )
    ).first()
    if existing is None:
        db.add(ScenarioRisk(scenario_id=scenario_id, risk_id=risk_id))
        db.commit()
    return _to_out(db, scenario)


@router.delete("/{scenario_id}/risks/{risk_id}", status_code=status.HTTP_204_NO_CONTENT)
def unlink_risk(
    scenario_id: uuid.UUID,
    risk_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(MANAGE_SCENARIOS)),
):
    db.query(ScenarioRisk).filter(
        ScenarioRisk.scenario_id == scenario_id, ScenarioRisk.risk_id == risk_id
    ).delete()
    db.commit()


@router.get("/{scenario_id}/exposure", response_model=ScenarioExposureOut)
def get_scenario_exposure(
    scenario_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(VIEW_RISKS)),
):
    """Read-only combined exposure snapshot: which linked risks are ready
    for a portfolio run and which aren't (missing their own simulation
    config yet), plus the most recent portfolio run if one exists.
    Deliberately does not trigger a new simulation itself — every run in
    this platform is an explicit POST, never a side effect of a GET (see
    the Milestone 7 plan for the full rationale)."""
    scenario = _get_scenario_or_404(db, scenario_id)
    risk_ids = _linked_risk_ids(db, scenario_id)

    missing = [
        risk_id for risk_id in risk_ids if get_latest_config_for_risk(db, risk_id) is None
    ]
    latest_run = db.scalars(
        select(SimulationRun)
        .where(SimulationRun.scenario_id == scenario_id)
        .order_by(SimulationRun.created_at.desc())
    ).first()

    return ScenarioExposureOut(
        scenario_id=scenario.id,
        linked_risk_count=len(risk_ids),
        risks_missing_simulation_config=missing,
        latest_run_id=latest_run.id if latest_run else None,
    )
