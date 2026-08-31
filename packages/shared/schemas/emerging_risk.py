from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from packages.shared.models.emerging_risk import CandidateLifecycleStatus


class EmergingSignalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_adapter: str
    source_citation: str
    raw_content: str
    classification: str | None
    ingested_at: datetime


class EmergingRiskCandidateOut(BaseModel):
    id: uuid.UUID
    title: str
    summary: str
    category_id: uuid.UUID | None
    category_name: str | None
    relevance_assessment: str
    model: str | None
    lifecycle_status: CandidateLifecycleStatus
    matched_risk_id: uuid.UUID | None
    created_risk_id: uuid.UUID | None
    reviewed_by_id: uuid.UUID | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    signals: list[EmergingSignalOut] = []


class CandidateTransitionIn(BaseModel):
    lifecycle_status: CandidateLifecycleStatus


class LinkExistingRiskIn(BaseModel):
    risk_id: uuid.UUID


class IngestJobOut(BaseModel):
    job_id: uuid.UUID
