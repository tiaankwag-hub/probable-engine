from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.shared.db import Base
from packages.shared.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class ImpactDimension(str, enum.Enum):
    FINANCIAL = "financial"
    CUSTOMER_SERVICE = "customer_service"
    OPERATIONAL_DELIVERY = "operational_delivery"
    LEGAL_REGULATORY = "legal_regulatory"
    REPUTATION = "reputation"
    HEALTH_SAFETY = "health_safety"


class RiskBand(str, enum.Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    EXTREME = "extreme"


class RiskStatus(str, enum.Enum):
    DRAFT = "draft"
    OPEN = "open"
    MONITORING = "monitoring"
    CLOSED = "closed"


class RiskDecision(str, enum.Enum):
    ACCEPT = "accept"
    TREAT = "treat"
    TRANSFER = "transfer"
    AVOID = "avoid"
    PENDING = "pending"


class RiskCategory(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "risk_categories"

    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("risk_categories.id"), nullable=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class Risk(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "risks"

    risk_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    statement: Mapped[str | None] = mapped_column(Text, nullable=True)
    cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    event: Mapped[str | None] = mapped_column(Text, nullable=True)
    impact: Mapped[str | None] = mapped_column(Text, nullable=True)

    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("risk_categories.id"), nullable=True
    )
    business_process: Mapped[str | None] = mapped_column(String(300), nullable=True)
    department: Mapped[str | None] = mapped_column(String(200), nullable=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    accountable_executive_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    status: Mapped[RiskStatus] = mapped_column(
        Enum(RiskStatus, name="risk_status"), default=RiskStatus.DRAFT, nullable=False
    )
    decision: Mapped[RiskDecision] = mapped_column(
        Enum(RiskDecision, name="risk_decision"), default=RiskDecision.PENDING, nullable=False
    )
    acceptance_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)

    raised_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_review_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Computed by packages/risk_engine only — never set directly by a user or import.
    likelihood: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overall_impact: Mapped[float | None] = mapped_column(nullable=True)
    inherent_score: Mapped[float | None] = mapped_column(nullable=True)
    inherent_band: Mapped[RiskBand | None] = mapped_column(
        Enum(RiskBand, name="risk_band_inherent"), nullable=True
    )
    control_effectiveness: Mapped[float | None] = mapped_column(nullable=True)
    residual_score: Mapped[float | None] = mapped_column(nullable=True)
    residual_band: Mapped[RiskBand | None] = mapped_column(
        Enum(RiskBand, name="risk_band_residual"), nullable=True
    )

    velocity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(50), nullable=True)
    treatment_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    latest_update: Mapped[str | None] = mapped_column(Text, nullable=True)

    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    category: Mapped[RiskCategory | None] = relationship()
    assessments: Mapped[list["RiskAssessment"]] = relationship(
        back_populates="risk", order_by="RiskAssessment.assessed_at.desc()"
    )
    history: Mapped[list["RiskHistory"]] = relationship(
        back_populates="risk", order_by="RiskHistory.version.desc()"
    )


class RiskAssessment(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "risk_assessments"

    risk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("risks.id", ondelete="CASCADE"), nullable=False
    )
    likelihood: Mapped[int] = mapped_column(Integer, nullable=False)
    overall_impact: Mapped[float] = mapped_column(nullable=False)
    inherent_score: Mapped[float] = mapped_column(nullable=False)
    inherent_band: Mapped[RiskBand] = mapped_column(Enum(RiskBand, name="risk_band_inherent"))
    control_effectiveness: Mapped[float | None] = mapped_column(nullable=True)
    residual_score: Mapped[float | None] = mapped_column(nullable=True)
    residual_band: Mapped[RiskBand | None] = mapped_column(
        Enum(RiskBand, name="risk_band_residual"), nullable=True
    )
    scoring_config_version: Mapped[int] = mapped_column(Integer, nullable=False)
    assessed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    risk: Mapped[Risk] = relationship(back_populates="assessments")
    impact_scores: Mapped[list["RiskImpactScore"]] = relationship(back_populates="assessment")


class RiskImpactScore(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "risk_impact_scores"

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("risk_assessments.id", ondelete="CASCADE"), nullable=False
    )
    dimension: Mapped[ImpactDimension] = mapped_column(
        Enum(ImpactDimension, name="impact_dimension"), nullable=False
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)

    assessment: Mapped[RiskAssessment] = relationship(back_populates="impact_scores")


class RiskHistory(Base, UUIDPrimaryKeyMixin):
    """Append-only. Never updated or deleted at the application layer."""

    __tablename__ = "risk_history"

    risk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("risks.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    field_state: Mapped[dict] = mapped_column(JSONB, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor: Mapped[str | None] = mapped_column(String(320), nullable=True)

    risk: Mapped[Risk] = relationship(back_populates="history")
