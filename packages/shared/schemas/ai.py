from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from packages.shared.models.ai import AICapability, AIRunStatus, AISuggestionReviewStatus


class RiskAnalysisRequest(BaseModel):
    risk_id: uuid.UUID


# Same shape as RiskAnalysisRequest — control-gap analysis is also a
# single-risk request — aliased for readability at the call site.
ControlGapAnalysisRequest = RiskAnalysisRequest


class AISuggestionOut(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    risk_id: uuid.UUID | None
    suggestion_type: str
    summary: str
    rationale: str
    proposed_changes: dict[str, Any]
    human_review_status: AISuggestionReviewStatus
    reviewed_by_id: uuid.UUID | None
    reviewed_at: datetime | None
    created_at: datetime


class AIRunOut(BaseModel):
    id: uuid.UUID
    capability: AICapability
    model: str | None
    prompt_version: str
    status: AIRunStatus
    narrative: str | None
    latency_ms: int | None
    error: str | None
    created_at: datetime
    completed_at: datetime | None
    suggestions: list[AISuggestionOut] = []
