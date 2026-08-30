from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.deps import get_db, require_permission
from packages.shared.models.risk import RiskCategory
from packages.shared.rbac import VIEW_RISKS
from packages.shared.schemas.category import RiskCategoryOut

router = APIRouter(prefix="/api/v1/risk-categories", tags=["categories"])


@router.get("", response_model=list[RiskCategoryOut])
def list_categories(
    db: Session = Depends(get_db),
    _user=Depends(require_permission(VIEW_RISKS)),
):
    return db.scalars(select(RiskCategory).order_by(RiskCategory.name)).all()
