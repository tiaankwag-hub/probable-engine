from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.app.deps import CurrentUser, get_db, require_permission
from packages.shared.dashboard_service import compute_executive_dashboard
from packages.shared.governance_service import compute_governance_health
from packages.shared.rbac import VIEW_RISKS
from packages.shared.schemas.dashboard import ExecutiveDashboard
from packages.shared.schemas.governance import GovernanceHealth

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/executive", response_model=ExecutiveDashboard)
def get_executive_dashboard(
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(VIEW_RISKS)),
):
    return compute_executive_dashboard(db)


@router.get("/governance", response_model=GovernanceHealth)
def get_governance_health(
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(VIEW_RISKS)),
):
    return compute_governance_health(db)
