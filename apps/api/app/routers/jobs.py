from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from apps.api.app.deps import CurrentUser, get_db, require_permission
from packages.shared.models.jobs import BackgroundJob
from packages.shared.rbac import VIEW_RISKS

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


class BackgroundJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_type: str
    status: str
    error: str | None


@router.get("/{job_id}", response_model=BackgroundJobOut)
def get_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(VIEW_RISKS)),
):
    job = db.get(BackgroundJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return BackgroundJobOut(id=job.id, job_type=job.job_type, status=job.status.value, error=job.error)
