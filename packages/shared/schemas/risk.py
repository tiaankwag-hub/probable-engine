from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.shared.models.risk import ImpactDimension, RiskBand, RiskDecision, RiskStatus


class ImpactScoresIn(BaseModel):
    financial: int = Field(ge=1, le=5)
    customer_service: int = Field(ge=1, le=5)
    operational_delivery: int = Field(ge=1, le=5)
    legal_regulatory: int = Field(ge=1, le=5)
    reputation: int = Field(ge=1, le=5)
    health_safety: int = Field(ge=1, le=5)


class ImpactScoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dimension: ImpactDimension
    score: int


class RiskAssessmentIn(BaseModel):
    likelihood: int = Field(ge=1, le=5)
    impact_scores: ImpactScoresIn
    control_effectiveness: int | None = Field(default=None, ge=1, le=5)


class RiskAssessmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    likelihood: int
    overall_impact: float
    inherent_score: float
    inherent_band: RiskBand
    control_effectiveness: int | None
    residual_score: float | None
    residual_band: RiskBand | None
    scoring_config_version: int
    assessed_at: datetime
    impact_scores: list[ImpactScoreOut] = []


class RiskCreate(BaseModel):
    risk_code: str | None = Field(default=None, max_length=50)
    title: str = Field(max_length=300)
    statement: str | None = None
    cause: str | None = None
    event: str | None = None
    impact: str | None = None
    category_id: uuid.UUID | None = None
    business_process: str | None = None
    department: str | None = None
    owner_id: uuid.UUID | None = None
    accountable_executive_id: uuid.UUID | None = None
    status: RiskStatus = RiskStatus.DRAFT
    decision: RiskDecision = RiskDecision.PENDING
    acceptance_rationale: str | None = None
    raised_date: date | None = None
    next_review_date: date | None = None
    velocity: str | None = None
    confidence: str | None = None
    treatment_summary: str | None = None
    latest_update: str | None = None
    assessment: RiskAssessmentIn

    @model_validator(mode="after")
    def acceptance_requires_rationale(self) -> "RiskCreate":
        if self.decision == RiskDecision.ACCEPT and not self.acceptance_rationale:
            raise ValueError("acceptance_rationale is required when decision is 'accept'")
        return self


class RiskUpdate(BaseModel):
    version: int
    title: str | None = Field(default=None, max_length=300)
    statement: str | None = None
    cause: str | None = None
    event: str | None = None
    impact: str | None = None
    category_id: uuid.UUID | None = None
    business_process: str | None = None
    department: str | None = None
    owner_id: uuid.UUID | None = None
    accountable_executive_id: uuid.UUID | None = None
    status: RiskStatus | None = None
    decision: RiskDecision | None = None
    acceptance_rationale: str | None = None
    raised_date: date | None = None
    next_review_date: date | None = None
    velocity: str | None = None
    confidence: str | None = None
    treatment_summary: str | None = None
    latest_update: str | None = None
    assessment: RiskAssessmentIn | None = None


class RiskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    risk_code: str
    title: str
    statement: str | None
    cause: str | None
    event: str | None
    impact: str | None
    category_id: uuid.UUID | None
    business_process: str | None
    department: str | None
    owner_id: uuid.UUID | None
    accountable_executive_id: uuid.UUID | None
    status: RiskStatus
    decision: RiskDecision
    acceptance_rationale: str | None
    raised_date: date | None
    next_review_date: date | None
    likelihood: int | None
    overall_impact: float | None
    inherent_score: float | None
    inherent_band: RiskBand | None
    control_effectiveness: float | None
    residual_score: float | None
    residual_band: RiskBand | None
    velocity: str | None
    confidence: str | None
    treatment_summary: str | None
    latest_update: str | None
    created_at: datetime
    updated_at: datetime
    version: int


class RiskHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    field_state: dict
    recorded_at: datetime
    actor: str | None


class PaginatedRisks(BaseModel):
    items: list[RiskOut]
    total: int
    page: int
    page_size: int
