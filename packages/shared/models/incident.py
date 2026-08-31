from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.shared.db import Base
from packages.shared.models.base import UUIDPrimaryKeyMixin


class IncidentSeverity(str, enum.Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class Incident(Base, UUIDPrimaryKeyMixin):
    """`review_triggered_at` is set only by the explicit
    `POST /incidents/{id}/trigger-review` action, never automatically on
    create — an incident is evidence a human reviews, not a silent risk
    mutation (domain model: "subject to human confirmation, not automatic
    silent change")."""

    __tablename__ = "incidents"

    incident_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    risk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("risks.id", ondelete="SET NULL"), nullable=True
    )
    control_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("controls.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    incident_date: Mapped[date] = mapped_column(Date, nullable=False)
    severity: Mapped[IncidentSeverity] = mapped_column(
        Enum(IncidentSeverity, name="incident_severity"), nullable=False
    )
    suggests_likelihood_increase: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    review_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
