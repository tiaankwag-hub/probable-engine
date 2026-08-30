from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.deps import CurrentUser, get_db, require_permission
from packages.shared.audit import record_audit_event
from packages.shared.models.scoring import ScoringConfig
from packages.shared.rbac import MANAGE_SCORING_CONFIG, VIEW_RISKS
from packages.shared.schemas.scoring_config import ScoringConfigIn, ScoringConfigOut

router = APIRouter(prefix="/api/v1/scoring-config", tags=["scoring-config"])


@router.get("", response_model=list[ScoringConfigOut])
def list_scoring_configs(
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(VIEW_RISKS)),
):
    rows = db.scalars(select(ScoringConfig).order_by(ScoringConfig.version.desc())).all()
    return [ScoringConfigOut.from_model(row) for row in rows]


@router.post("", response_model=ScoringConfigOut, status_code=201)
def create_scoring_config(
    payload: ScoringConfigIn,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(MANAGE_SCORING_CONFIG)),
):
    """Creates a new scoring-config version and makes it the active one.
    Past risk_assessments keep referencing their original
    scoring_config_version, so this never changes how a historical score is
    explained (ADR 0007) — only new assessments use the new config."""
    max_version = db.scalar(select(ScoringConfig.version).order_by(ScoringConfig.version.desc()))
    new_version = (max_version or 0) + 1

    db.query(ScoringConfig).filter(ScoringConfig.is_active.is_(True)).update({"is_active": False})

    config_json = {
        "dimension_weights": payload.dimension_weights,
        "band_thresholds": [list(t) for t in payload.band_thresholds],
        "max_reduction_fraction": payload.max_reduction_fraction,
        "max_control_effectiveness": payload.max_control_effectiveness,
    }
    row = ScoringConfig(
        version=new_version,
        config=config_json,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        created_by=current_user.user.id,
    )
    db.add(row)
    db.flush()

    record_audit_event(
        db,
        actor=current_user.email,
        entity="scoring_config",
        entity_id=row.id,
        action="create",
        old_value=None,
        new_value=config_json,
        source="ui",
    )
    db.commit()
    db.refresh(row)
    return ScoringConfigOut.from_model(row)
