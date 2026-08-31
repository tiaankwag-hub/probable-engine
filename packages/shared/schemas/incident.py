from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from packages.shared.models.incident import IncidentSeverity


class IncidentCreate(BaseModel):
    risk_id: uuid.UUID | None = None
    control_id: uuid.UUID | None = None
    description: str
    incident_date: date
    severity: IncidentSeverity
    suggests_likelihood_increase: bool = False


class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    incident_code: str
    risk_id: uuid.UUID | None
    control_id: uuid.UUID | None
    description: str
    incident_date: date
    severity: IncidentSeverity
    suggests_likelihood_increase: bool
    review_triggered_at: datetime | None
    created_at: datetime
    updated_at: datetime
