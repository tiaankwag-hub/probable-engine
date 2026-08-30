from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.deps import CurrentUser, get_db, require_permission
from packages.shared.audit import record_audit_event
from packages.shared.models.risk_appetite import RiskAppetite
from packages.shared.rbac import MANAGE_APPETITE, VIEW_RISKS
from packages.shared.schemas.appetite import RiskAppetiteIn, RiskAppetiteOut

router = APIRouter(prefix="/api/v1/risk-appetite", tags=["risk-appetite"])


@router.get("", response_model=list[RiskAppetiteOut])
def list_appetite(
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(VIEW_RISKS)),
):
    return db.scalars(select(RiskAppetite).order_by(RiskAppetite.effective_from.desc())).all()


@router.post("", response_model=RiskAppetiteOut, status_code=status.HTTP_201_CREATED)
def create_appetite(
    payload: RiskAppetiteIn,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(MANAGE_APPETITE)),
):
    row = RiskAppetite(**payload.model_dump())
    db.add(row)
    db.flush()
    record_audit_event(
        db, actor=current_user.email, entity="risk_appetite", entity_id=row.id, action="create",
        old_value=None, new_value=payload.model_dump(mode="json"), source="ui",
    )
    db.commit()
    db.refresh(row)
    return row


@router.patch("/{appetite_id}", response_model=RiskAppetiteOut)
def update_appetite(
    appetite_id: uuid.UUID,
    payload: RiskAppetiteIn,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(MANAGE_APPETITE)),
):
    row = db.get(RiskAppetite, appetite_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="appetite config not found")
    old_value = {
        "appetite_band": row.appetite_band,
        "tolerance_band": row.tolerance_band,
        "limit_value": float(row.limit_value) if row.limit_value is not None else None,
    }
    for field_name, value in payload.model_dump().items():
        setattr(row, field_name, value)
    db.flush()
    record_audit_event(
        db, actor=current_user.email, entity="risk_appetite", entity_id=row.id, action="update",
        old_value=old_value, new_value=payload.model_dump(mode="json"), source="ui",
    )
    db.commit()
    db.refresh(row)
    return row
