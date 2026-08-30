from __future__ import annotations

import enum
import uuid
from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.shared.db import Base
from packages.shared.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class ActionPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ActionStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Action(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "actions"

    action_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    risk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("risks.id", ondelete="CASCADE"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    priority: Mapped[ActionPriority] = mapped_column(
        Enum(ActionPriority, name="action_priority"), default=ActionPriority.MEDIUM, nullable=False
    )
    status: Mapped[ActionStatus] = mapped_column(
        Enum(ActionStatus, name="action_status"), default=ActionStatus.OPEN, nullable=False
    )
    completion_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expected_risk_reduction: Mapped[float | None] = mapped_column(nullable=True)
    evidence: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    completed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
