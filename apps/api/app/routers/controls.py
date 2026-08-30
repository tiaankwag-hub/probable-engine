from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.app.deps import CurrentUser, get_db, require_permission
from packages.shared.audit import record_audit_event
from packages.shared.models.control import Control, ControlTest, ControlTestResult
from packages.shared.rbac import (
    CREATE_CONTROL,
    MANAGE_ANY_CONTROL,
    MANAGE_OWN_CONTROL,
    VIEW_RISKS,
    role_has_permission,
)
from packages.shared.schemas.control import ControlIn, ControlOut, ControlTestIn, ControlTestOut

router = APIRouter(prefix="/api/v1/controls", tags=["controls"])

RESULT_TO_EFFECTIVENESS = {
    ControlTestResult.EFFECTIVE: 5,
    ControlTestResult.PARTIALLY_EFFECTIVE: 3,
    ControlTestResult.INEFFECTIVE: 1,
}


def _can_manage(current_user: CurrentUser, control: Control) -> bool:
    if any(role_has_permission(r, MANAGE_ANY_CONTROL) for r in current_user.roles):
        return True
    if any(role_has_permission(r, MANAGE_OWN_CONTROL) for r in current_user.roles):
        return control.owner_id == current_user.user.id
    return False


def _generate_control_code(session: Session) -> str:
    count = session.scalar(select(func.count()).select_from(Control)) or 0
    candidate = f"CTRL-{count + 1:04d}"
    while session.scalar(select(Control.id).where(Control.control_code == candidate)):
        count += 1
        candidate = f"CTRL-{count + 1:04d}"
    return candidate


@router.get("", response_model=list[ControlOut])
def list_controls(
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(VIEW_RISKS)),
):
    return db.scalars(select(Control).order_by(Control.control_code)).all()


@router.post("", response_model=ControlOut, status_code=status.HTTP_201_CREATED)
def create_control(
    payload: ControlIn,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(CREATE_CONTROL)),
):
    control = Control(
        control_code=payload.control_code or _generate_control_code(db),
        name=payload.name,
        description=payload.description,
        control_type=payload.control_type,
        automation=payload.automation,
        owner_id=payload.owner_id or current_user.user.id,
        frequency=payload.frequency,
        design_effectiveness=payload.design_effectiveness,
        operating_effectiveness=payload.operating_effectiveness,
        last_tested=payload.last_tested,
        next_test=payload.next_test,
        status=payload.status,
    )
    db.add(control)
    db.flush()
    record_audit_event(
        db, actor=current_user.email, entity="control", entity_id=control.id, action="create",
        old_value=None, new_value={"control_code": control.control_code, "name": control.name},
        source="ui",
    )
    db.commit()
    db.refresh(control)
    return control


@router.get("/{control_id}", response_model=ControlOut)
def get_control(
    control_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(VIEW_RISKS)),
):
    control = db.get(Control, control_id)
    if control is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="control not found")
    return control


@router.patch("/{control_id}", response_model=ControlOut)
def update_control(
    control_id: uuid.UUID,
    payload: ControlIn,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(VIEW_RISKS)),
):
    control = db.get(Control, control_id)
    if control is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="control not found")
    if not _can_manage(current_user, control):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="cannot manage this control")

    old_value = {
        "design_effectiveness": control.design_effectiveness,
        "operating_effectiveness": control.operating_effectiveness,
        "status": control.status.value,
    }
    for field_name, value in payload.model_dump(exclude={"control_code"}, exclude_unset=True).items():
        setattr(control, field_name, value)
    db.flush()

    record_audit_event(
        db, actor=current_user.email, entity="control", entity_id=control.id, action="update",
        old_value=old_value,
        new_value={
            "design_effectiveness": control.design_effectiveness,
            "operating_effectiveness": control.operating_effectiveness,
            "status": control.status.value,
        },
        source="ui",
    )
    db.commit()
    db.refresh(control)
    return control


@router.get("/{control_id}/tests", response_model=list[ControlTestOut])
def list_control_tests(
    control_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(VIEW_RISKS)),
):
    control = db.get(Control, control_id)
    if control is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="control not found")
    return control.tests


@router.post("/{control_id}/tests", response_model=ControlTestOut, status_code=status.HTTP_201_CREATED)
def record_control_test(
    control_id: uuid.UUID,
    payload: ControlTestIn,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(VIEW_RISKS)),
):
    """Recording a test is how a control's `operating_effectiveness` moves —
    it is never edited directly, only derived from the most recent test
    result (domain model: control_tests feed the ongoing effectiveness
    rating). A test result of 'not_tested' leaves the rating unchanged."""
    control = db.get(Control, control_id)
    if control is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="control not found")
    if not _can_manage(current_user, control):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="cannot manage this control")

    test = ControlTest(
        control_id=control_id,
        tester=payload.tester,
        test_date=payload.test_date,
        test_method=payload.test_method,
        result=payload.result,
        finding=payload.finding,
        remediation_action=payload.remediation_action,
        created_at=datetime.now(timezone.utc),
    )
    db.add(test)
    db.flush()

    if control.last_tested is None or payload.test_date >= control.last_tested:
        control.last_tested = payload.test_date
        if payload.result in RESULT_TO_EFFECTIVENESS:
            control.operating_effectiveness = RESULT_TO_EFFECTIVENESS[payload.result]

    record_audit_event(
        db, actor=current_user.email, entity="control_test", entity_id=test.id, action="create",
        old_value=None,
        new_value={"result": payload.result.value, "test_date": payload.test_date.isoformat()},
        source="ui",
    )
    db.commit()
    db.refresh(test)
    return test
