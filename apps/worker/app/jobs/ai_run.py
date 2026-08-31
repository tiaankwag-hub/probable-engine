from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from packages.ai.factory import get_provider
from packages.shared.ai_service import execute_executive_summary, execute_risk_analysis
from packages.shared.models.ai import AICapability, AIRun, AIRunStatus
from packages.shared.models.risk import Risk
from packages.shared.storage import ObjectStore


def handle(session: Session, payload: dict, _object_store: ObjectStore) -> None:
    run = session.get(AIRun, uuid.UUID(payload["run_id"]))
    if run is None:
        raise ValueError(f"AI run not found: {payload['run_id']}")

    now = datetime.now(timezone.utc)
    run.status = AIRunStatus.RUNNING
    run.updated_at = now
    session.commit()

    provider = get_provider()
    try:
        if run.capability == AICapability.EXECUTIVE_SUMMARY:
            execute_executive_summary(session, provider, run)
        elif run.capability == AICapability.RISK_ANALYSIS:
            risk_id = uuid.UUID(payload["risk_id"])
            risk = session.get(Risk, risk_id)
            if risk is None:
                raise ValueError(f"risk not found: {risk_id}")
            execute_risk_analysis(session, provider, run, risk=risk)
        else:
            raise ValueError(f"unknown AI capability: {run.capability}")
    except Exception as exc:  # noqa: BLE001 - surfaced on the run so the UI shows it
        run.status = AIRunStatus.FAILED
        run.error = str(exc)
        run.completed_at = datetime.now(timezone.utc)
        run.updated_at = run.completed_at
        session.commit()
        raise

    session.commit()
