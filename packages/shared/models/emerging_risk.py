"""Emerging Risk Radar (Milestone 9, docs/architecture/02-domain-model.md's
"Emerging risk radar" section). An `EmergingSignal` is a raw ingested item
from a signal adapter (`packages/emerging_risk`) — never itself
authoritative, just a record of what was seen and where it came from. An
`EmergingRiskCandidate` is derived from one or more signals (see
`emerging_candidate_signals`); `packages/ai`'s `analyze_signal` capability
can create or update a candidate directly (it starts and can stay
`candidate`/`under_review` — an inherently non-authoritative state), but
only a human lifecycle transition (via the API, audited) can move one to
`accepted` (which creates a real `Risk`, always with a minimal, unrated
placeholder assessment) or `linked_to_existing` (which points at an
already-registered `Risk` instead of creating a new one). There is no
code path from this module to `risks` other than through that human
transition — see `packages/shared/emerging_risk_service.py`.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.shared.db import Base
from packages.shared.models.base import UUIDPrimaryKeyMixin
from packages.shared.models.risk import RiskCategory


class CandidateLifecycleStatus(str, enum.Enum):
    CANDIDATE = "candidate"
    UNDER_REVIEW = "under_review"
    ACCEPTED = "accepted"
    LINKED_TO_EXISTING = "linked_to_existing"
    DISMISSED = "dismissed"


class EmergingSignal(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "emerging_signals"
    __table_args__ = (UniqueConstraint("source_citation", name="uq_emerging_signal_source_citation"),)

    source_adapter: Mapped[str] = mapped_column(String(100), nullable=False)
    source_citation: Mapped[str] = mapped_column(String(500), nullable=False)
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    classification: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EmergingRiskCandidate(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "emerging_risk_candidates"

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("risk_categories.id"), nullable=True
    )
    relevance_assessment: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lifecycle_status: Mapped[CandidateLifecycleStatus] = mapped_column(
        Enum(CandidateLifecycleStatus, name="candidate_lifecycle_status"),
        default=CandidateLifecycleStatus.CANDIDATE,
        nullable=False,
    )
    matched_risk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("risks.id"), nullable=True
    )
    created_risk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("risks.id"), nullable=True
    )
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    category: Mapped[RiskCategory | None] = relationship()


class EmergingCandidateSignal(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "emerging_candidate_signals"
    __table_args__ = (
        UniqueConstraint("candidate_id", "signal_id", name="uq_emerging_candidate_signal"),
    )

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("emerging_risk_candidates.id", ondelete="CASCADE"), nullable=False
    )
    signal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("emerging_signals.id", ondelete="CASCADE"), nullable=False
    )
