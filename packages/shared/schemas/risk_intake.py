from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from packages.shared.models.risk_intake import IntakeSessionStatus


class IntakeMessageOut(BaseModel):
    role: str
    content: str


class RiskIntakeSessionOut(BaseModel):
    id: uuid.UUID
    status: IntakeSessionStatus
    transcript: list[IntakeMessageOut]
    draft_fields: dict[str, str]
    turn_count: int
    model: str | None
    initiated_by_id: uuid.UUID
    initiated_by_email: str
    resulting_risk_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class IntakeMessageIn(BaseModel):
    message: str


class IntakeSubmitOut(BaseModel):
    risk_id: uuid.UUID
    risk_code: str
