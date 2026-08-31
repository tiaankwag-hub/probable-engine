from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.app.deps import CurrentUser, get_db, require_permission
from packages.shared.audit import record_audit_event
from packages.shared.models.issue import Issue
from packages.shared.rbac import CREATE_ISSUE, VIEW_RISKS
from packages.shared.schemas.issue import IssueCreate, IssueOut, IssueUpdate

router = APIRouter(prefix="/api/v1/issues", tags=["issues"])


def _generate_issue_code(session: Session) -> str:
    count = session.scalar(select(func.count()).select_from(Issue)) or 0
    candidate = f"ISS-{count + 1:04d}"
    while session.scalar(select(Issue.id).where(Issue.issue_code == candidate)):
        count += 1
        candidate = f"ISS-{count + 1:04d}"
    return candidate


@router.get("", response_model=list[IssueOut])
def list_issues(
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(VIEW_RISKS)),
):
    return db.scalars(select(Issue).order_by(Issue.created_at.desc())).all()


@router.post("", response_model=IssueOut, status_code=status.HTTP_201_CREATED)
def create_issue(
    payload: IssueCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(CREATE_ISSUE)),
):
    now = datetime.now(timezone.utc)
    issue = Issue(
        issue_code=_generate_issue_code(db),
        risk_id=payload.risk_id,
        control_id=payload.control_id,
        description=payload.description,
        source=payload.source,
        created_at=now,
        updated_at=now,
    )
    db.add(issue)
    db.flush()
    record_audit_event(
        db, actor=current_user.email, entity="issue", entity_id=issue.id, action="create",
        old_value=None, new_value={"description": issue.description}, source="ui",
    )
    db.commit()
    db.refresh(issue)
    return issue


@router.patch("/{issue_id}", response_model=IssueOut)
def update_issue(
    issue_id: uuid.UUID,
    payload: IssueUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(VIEW_RISKS)),
):
    issue = db.get(Issue, issue_id)
    if issue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="issue not found")
    old_status = issue.status.value
    issue.status = payload.status
    issue.updated_at = datetime.now(timezone.utc)
    db.flush()
    record_audit_event(
        db, actor=current_user.email, entity="issue", entity_id=issue.id, action="update",
        old_value={"status": old_status}, new_value={"status": issue.status.value}, source="ui",
    )
    db.commit()
    db.refresh(issue)
    return issue
