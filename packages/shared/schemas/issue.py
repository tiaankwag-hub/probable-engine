from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from packages.shared.models.issue import IssueStatus


class IssueCreate(BaseModel):
    risk_id: uuid.UUID | None = None
    control_id: uuid.UUID | None = None
    description: str
    source: str | None = None


class IssueUpdate(BaseModel):
    status: IssueStatus


class IssueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    issue_code: str
    risk_id: uuid.UUID | None
    control_id: uuid.UUID | None
    description: str
    source: str | None
    status: IssueStatus
    created_at: datetime
    updated_at: datetime
