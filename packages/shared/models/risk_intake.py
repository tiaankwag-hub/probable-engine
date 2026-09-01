"""Guided Risk Intake (post-Milestone-9 enhancement, ADR 0006 extended): a
conversational, iterative-questioning path for a regular user or executive
who wants to raise a risk but doesn't know the register's terminology. An
AI capability turns their free-text answers into a structured draft —
title, cause, event, impact, a category guess — but never assigns a score
and never writes to `risks` directly. Finishing a session creates a real
`Risk` row through the exact same `packages.shared.risk_service.create_risk`
path every other risk-creation route uses, always `draft` status with the
same minimal, unrated placeholder assessment principle as an approved
emerging-risk suggestion — a Risk Manager reviews and completes it from
there like any other draft, with the full conversation kept for context.

Unlike every other AI capability in this codebase (which runs as a single
`BackgroundJob`, see ADR 0005), a session is driven by live, synchronous
API calls — one per chat turn — because a conversation needs to feel like
a conversation, not a poll loop.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.shared.db import Base
from packages.shared.models.base import UUIDPrimaryKeyMixin


class IntakeSessionStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    READY_TO_SUBMIT = "ready_to_submit"
    SUBMITTED = "submitted"
    ABANDONED = "abandoned"


class RiskIntakeSession(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "risk_intake_sessions"

    initiated_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    status: Mapped[IntakeSessionStatus] = mapped_column(
        Enum(IntakeSessionStatus, name="intake_session_status"),
        default=IntakeSessionStatus.IN_PROGRESS,
        nullable=False,
    )
    transcript: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    """[{"role": "assistant"|"user", "content": str}, ...], oldest first."""
    draft_fields: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    """The structured risk being assembled turn by turn: title, statement,
    cause, event, impact, category_guess, department_guess — never a
    numeric score, per the placeholder-assessment principle above."""
    turn_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resulting_risk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("risks.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
