from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.app.deps import CurrentUser, get_db, require_permission
from packages.shared.models.snapshot import Snapshot, SnapshotRisk
from packages.shared.rbac import MANAGE_SNAPSHOTS, VIEW_RISKS
from packages.shared.schemas.snapshot import (
    SnapshotCreate,
    SnapshotOut,
    TrendPoint,
    WhatChanged,
)
from packages.shared.snapshot_service import capture_snapshot, compute_trend, compute_what_changed

router = APIRouter(prefix="/api/v1/snapshots", tags=["snapshots"])
dashboard_router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


def _to_out(session: Session, snapshot: Snapshot) -> SnapshotOut:
    risk_count = session.scalar(
        select(func.count()).select_from(SnapshotRisk).where(SnapshotRisk.snapshot_id == snapshot.id)
    ) or 0
    return SnapshotOut(
        id=snapshot.id, label=snapshot.label, period_end=snapshot.period_end,
        created_at=snapshot.created_at, risk_count=risk_count,
    )


@router.get("", response_model=list[SnapshotOut])
def list_snapshots(
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(VIEW_RISKS)),
):
    snapshots = db.scalars(select(Snapshot).order_by(Snapshot.period_end.desc())).all()
    return [_to_out(db, s) for s in snapshots]


@router.post("", response_model=SnapshotOut, status_code=status.HTTP_201_CREATED)
def create_snapshot(
    payload: SnapshotCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(MANAGE_SNAPSHOTS)),
):
    snapshot = capture_snapshot(
        db,
        label=payload.label,
        period_end=payload.period_end or date.today(),
        actor_email=current_user.email,
    )
    db.commit()
    db.refresh(snapshot)
    return _to_out(db, snapshot)


@dashboard_router.get("/what-changed", response_model=WhatChanged)
def get_what_changed(
    since_snapshot: uuid.UUID,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(VIEW_RISKS)),
):
    try:
        return compute_what_changed(db, since_snapshot)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None


@dashboard_router.get("/trends", response_model=list[TrendPoint])
def get_trends(
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(VIEW_RISKS)),
):
    return compute_trend(db)
