"""AI runs and suggestions (Milestone 8, ADR 0006). An `AIRun` is an
audit record of one provider call — model, prompt version, latency, raw
response — regardless of whether it produced any suggestion. An
`AISuggestion` is a structured, actionable proposal derived from a run;
it starts `pending` and can only ever become `approved` (which applies
`proposed_changes` through the normal, audited service-layer path for
its `suggestion_type` — `risk_service.update_risk` for an
`assessment_change`, `control_service.create_control` for a
`new_control`, `risk_service.create_risk` for a `new_risk` — each
producing its own `risk_history`/`audit_events` rows) or `rejected` by a
human. `risk_id` is null only for a `new_risk` suggestion, which by
definition has no existing risk to attach to yet. There is no code path
from this module to `risks`/`controls` directly — see
`packages/shared/ai_service.py`.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.shared.db import Base
from packages.shared.models.base import UUIDPrimaryKeyMixin


class AICapability(str, enum.Enum):
    EXECUTIVE_SUMMARY = "executive_summary"
    RISK_ANALYSIS = "risk_analysis"
    CONTROL_GAP_ANALYSIS = "control_gap_analysis"
    EMERGING_RISK_SCAN = "emerging_risk_scan"
    MARKET_ANALYSIS = "market_analysis"


class AIRunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AISuggestionReviewStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class AIRun(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "ai_runs"

    capability: Mapped[AICapability] = mapped_column(
        Enum(AICapability, name="ai_capability"), nullable=False
    )
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(20), nullable=False, default="v1")
    requested_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    input_risk_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    sources: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[AIRunStatus] = mapped_column(
        Enum(AIRunStatus, name="ai_run_status"), default=AIRunStatus.PENDING, nullable=False
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AISuggestion(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "ai_suggestions"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_runs.id", ondelete="CASCADE"), nullable=False
    )
    risk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("risks.id", ondelete="CASCADE"), nullable=True
    )
    suggestion_type: Mapped[str] = mapped_column(String(50), nullable=False)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_changes: Mapped[dict] = mapped_column(JSONB, nullable=False)
    human_review_status: Mapped[AISuggestionReviewStatus] = mapped_column(
        Enum(AISuggestionReviewStatus, name="ai_suggestion_review_status"),
        default=AISuggestionReviewStatus.PENDING,
        nullable=False,
    )
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
