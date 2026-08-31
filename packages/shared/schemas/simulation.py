from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from packages.shared.models.simulation import SimulationRunStatus
from packages.simulations.distributions import DistributionType

DEFAULT_ITERATIONS = 10_000


class SimulationConfigCreate(BaseModel):
    risk_id: uuid.UUID
    distribution_type: DistributionType
    loss_min: float = Field(gt=0)
    loss_most_likely: float = Field(gt=0)
    loss_max: float = Field(gt=0)
    annual_event_frequency: float = Field(default=1.0, ge=0)
    confidence: float | None = Field(default=None, ge=0, le=1)
    correlation_group: str | None = None
    correlation_strength: float | None = Field(default=None, ge=0, le=1)
    iterations: int = Field(default=DEFAULT_ITERATIONS, ge=100, le=200_000)
    seed: int = Field(default=42)


class SimulationConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    risk_id: uuid.UUID
    distribution_type: DistributionType
    loss_min: float
    loss_most_likely: float
    loss_max: float
    annual_event_frequency: float
    confidence: float | None
    correlation_group: str | None
    correlation_strength: float | None
    iterations: int
    seed: int
    created_at: datetime


class SimulationResultOut(BaseModel):
    expected_annual_loss: float
    median: float
    p75: float
    p90: float
    p95: float
    p99: float
    histogram: list[dict[str, Any]]
    per_risk_contribution: dict[str, float] | None


class SimulationRunOut(BaseModel):
    id: uuid.UUID
    config_id: uuid.UUID | None
    scenario_id: uuid.UUID | None
    status: SimulationRunStatus
    iterations_used: int
    seed_used: int
    error: str | None
    created_at: datetime
    completed_at: datetime | None
    result: SimulationResultOut | None = None
    config: SimulationConfigOut | None = None


class PortfolioSimulationRequest(BaseModel):
    scenario_id: uuid.UUID
    iterations: int = Field(default=DEFAULT_ITERATIONS, ge=100, le=200_000)
    seed: int = Field(default=42)
