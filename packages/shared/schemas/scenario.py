from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ScenarioCreate(BaseModel):
    name: str
    description: str | None = None
    assumptions: str | None = None
    duration_days: int | None = None
    financial_impact_min: float | None = None
    financial_impact_most_likely: float | None = None
    financial_impact_max: float | None = None
    operational_impact: str | None = None
    recovery_assumptions: str | None = None


class ScenarioUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    assumptions: str | None = None
    duration_days: int | None = None
    financial_impact_min: float | None = None
    financial_impact_most_likely: float | None = None
    financial_impact_max: float | None = None
    operational_impact: str | None = None
    recovery_assumptions: str | None = None


class ScenarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    assumptions: str | None
    duration_days: int | None
    financial_impact_min: float | None
    financial_impact_most_likely: float | None
    financial_impact_max: float | None
    operational_impact: str | None
    recovery_assumptions: str | None
    created_at: datetime
    updated_at: datetime
    linked_risk_ids: list[uuid.UUID] = []


class ScenarioExposureOut(BaseModel):
    scenario_id: uuid.UUID
    linked_risk_count: int
    risks_missing_simulation_config: list[uuid.UUID]
    latest_run_id: uuid.UUID | None
