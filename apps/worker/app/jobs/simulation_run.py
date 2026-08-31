from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from packages.shared.models.simulation import SimulationRun, SimulationRunStatus
from packages.shared.simulation_service import (
    run_scenario_portfolio_simulation,
    run_single_risk_simulation,
)
from packages.shared.storage import ObjectStore


def handle(session: Session, payload: dict, _object_store: ObjectStore) -> None:
    run = session.get(SimulationRun, uuid.UUID(payload["run_id"]))
    if run is None:
        raise ValueError(f"simulation run not found: {payload['run_id']}")

    now = datetime.now(timezone.utc)
    run.status = SimulationRunStatus.RUNNING
    run.started_at = now
    run.updated_at = now
    session.commit()

    try:
        if run.config_id is not None:
            run_single_risk_simulation(session, run)
        elif run.scenario_id is not None:
            run_scenario_portfolio_simulation(session, run)
        else:
            raise ValueError("simulation run has neither config_id nor scenario_id set")
    except Exception as exc:  # noqa: BLE001 - surfaced on the run so the UI shows it
        run.status = SimulationRunStatus.FAILED
        run.error = str(exc)
        run.completed_at = datetime.now(timezone.utc)
        run.updated_at = run.completed_at
        session.commit()
        raise

    run.status = SimulationRunStatus.SUCCEEDED
    run.completed_at = datetime.now(timezone.utc)
    run.updated_at = run.completed_at
    session.commit()
