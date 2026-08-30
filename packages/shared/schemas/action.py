from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from packages.shared.models.action import ActionPriority, ActionStatus


class ActionCreate(BaseModel):
    risk_id: uuid.UUID | None = None
    title: str = Field(max_length=300)
    description: str | None = None
    owner_id: uuid.UUID | None = None
    due_date: date | None = None
    priority: ActionPriority = ActionPriority.MEDIUM
    expected_risk_reduction: float | None = Field(default=None, ge=0, le=1)


class ActionUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    description: str | None = None
    owner_id: uuid.UUID | None = None
    due_date: date | None = None
    priority: ActionPriority | None = None
    status: ActionStatus | None = None
    completion_percent: int | None = Field(default=None, ge=0, le=100)
    expected_risk_reduction: float | None = Field(default=None, ge=0, le=1)
    completed_date: date | None = None


class ActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action_code: str
    risk_id: uuid.UUID | None
    title: str
    description: str | None
    owner_id: uuid.UUID | None
    due_date: date | None
    priority: ActionPriority
    status: ActionStatus
    completion_percent: int
    expected_risk_reduction: float | None
    evidence: str | None
    completed_date: date | None
    created_at: datetime
    updated_at: datetime
