"""Shared control-creation logic used by both apps/api (interactive CRUD)
and packages/shared/ai_service.py (a human-approved "new control" AI
suggestion), so the two never diverge on control-code generation or
audit-event shape — same rationale as risk_service.py for risks.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.shared.audit import record_audit_event
from packages.shared.models.control import Control, ControlAutomation, ControlStatus, ControlType


@dataclass
class ControlFields:
    name: str
    control_type: ControlType
    automation: ControlAutomation = ControlAutomation.MANUAL
    description: str | None = None
    owner_id: uuid.UUID | None = None
    frequency: str | None = None
    design_effectiveness: int | None = None
    operating_effectiveness: int | None = None
    last_tested: date | None = None
    next_test: date | None = None
    status: ControlStatus = ControlStatus.DRAFT


def generate_control_code(session: Session) -> str:
    count = session.scalar(select(func.count()).select_from(Control)) or 0
    candidate = f"CTRL-{count + 1:04d}"
    while session.scalar(select(Control.id).where(Control.control_code == candidate)):
        count += 1
        candidate = f"CTRL-{count + 1:04d}"
    return candidate


def create_control(
    session: Session,
    *,
    fields: ControlFields,
    actor_email: str,
    actor_id: uuid.UUID | None,
    source: str,
    control_code: str | None = None,
) -> Control:
    control = Control(
        control_code=control_code or generate_control_code(session),
        name=fields.name,
        description=fields.description,
        control_type=fields.control_type,
        automation=fields.automation,
        owner_id=fields.owner_id or actor_id,
        frequency=fields.frequency,
        design_effectiveness=fields.design_effectiveness,
        operating_effectiveness=fields.operating_effectiveness,
        last_tested=fields.last_tested,
        next_test=fields.next_test,
        status=fields.status,
    )
    session.add(control)
    session.flush()
    record_audit_event(
        session,
        actor=actor_email,
        entity="control",
        entity_id=control.id,
        action="create",
        old_value=None,
        new_value={"control_code": control.control_code, "name": control.name},
        source=source,
    )
    return control
