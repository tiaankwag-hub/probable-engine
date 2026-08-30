from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.app.deps import CurrentUser, get_current_user, get_db, require_permission
from packages.shared.audit import record_audit_event
from packages.shared.models.action import Action, ActionStatus
from packages.shared.rbac import (
    CREATE_ACTION,
    EDIT_ANY_ACTION,
    EDIT_OWN_ACTION,
    VIEW_RISKS,
    role_has_permission,
)
from packages.shared.schemas.action import ActionCreate, ActionOut, ActionUpdate

router = APIRouter(prefix="/api/v1/actions", tags=["actions"])

NON_TERMINAL_STATUSES = (ActionStatus.OPEN, ActionStatus.IN_PROGRESS)


def _can_edit(current_user: CurrentUser, action: Action) -> bool:
    if any(role_has_permission(r, EDIT_ANY_ACTION) for r in current_user.roles):
        return True
    if any(role_has_permission(r, EDIT_OWN_ACTION) for r in current_user.roles):
        return action.owner_id == current_user.user.id
    return False


def _generate_action_code(session: Session) -> str:
    count = session.scalar(select(func.count()).select_from(Action)) or 0
    candidate = f"ACT-{count + 1:04d}"
    while session.scalar(select(Action.id).where(Action.action_code == candidate)):
        count += 1
        candidate = f"ACT-{count + 1:04d}"
    return candidate


@router.get("", response_model=list[ActionOut])
def list_actions(
    overdue: bool | None = Query(default=None),
    status_filter: ActionStatus | None = Query(default=None, alias="status"),
    owner_id: uuid.UUID | None = None,
    risk_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(VIEW_RISKS)),
):
    query = select(Action)
    if status_filter is not None:
        query = query.where(Action.status == status_filter)
    if owner_id is not None:
        query = query.where(Action.owner_id == owner_id)
    if risk_id is not None:
        query = query.where(Action.risk_id == risk_id)
    if overdue:
        query = query.where(
            Action.due_date < date.today(), Action.status.in_(NON_TERMINAL_STATUSES)
        )
    return db.scalars(query.order_by(Action.due_date)).all()


@router.post("", response_model=ActionOut, status_code=status.HTTP_201_CREATED)
def create_action(
    payload: ActionCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(CREATE_ACTION)),
):
    action = Action(
        action_code=_generate_action_code(db),
        risk_id=payload.risk_id,
        title=payload.title,
        description=payload.description,
        owner_id=payload.owner_id or current_user.user.id,
        due_date=payload.due_date,
        priority=payload.priority,
        expected_risk_reduction=payload.expected_risk_reduction,
    )
    db.add(action)
    db.flush()
    record_audit_event(
        db, actor=current_user.email, entity="action", entity_id=action.id, action="create",
        old_value=None, new_value={"title": action.title, "risk_id": str(action.risk_id) if action.risk_id else None},
        source="ui",
    )
    db.commit()
    db.refresh(action)
    return action


@router.get("/{action_id}", response_model=ActionOut)
def get_action(
    action_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(VIEW_RISKS)),
):
    action = db.get(Action, action_id)
    if action is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="action not found")
    return action


@router.patch("/{action_id}", response_model=ActionOut)
def update_action(
    action_id: uuid.UUID,
    payload: ActionUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    action = db.get(Action, action_id)
    if action is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="action not found")
    if not _can_edit(current_user, action):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="cannot edit this action")

    old_value = {"status": action.status.value, "completion_percent": action.completion_percent}
    updates = payload.model_dump(exclude_unset=True)
    for field_name, value in updates.items():
        setattr(action, field_name, value)

    if action.status == ActionStatus.COMPLETED and action.completed_date is None:
        action.completed_date = date.today()
    if action.status == ActionStatus.COMPLETED and "completion_percent" not in updates:
        action.completion_percent = 100

    db.flush()
    record_audit_event(
        db, actor=current_user.email, entity="action", entity_id=action.id, action="update",
        old_value=old_value,
        new_value={"status": action.status.value, "completion_percent": action.completion_percent},
        source="ui",
    )
    db.commit()
    db.refresh(action)
    return action
