from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.shared.db import Base
from packages.shared.models.base import UUIDPrimaryKeyMixin


class IssueStatus(str, enum.Enum):
    OPEN = "open"
    RESOLVED = "resolved"


class Issue(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "issues"

    issue_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    risk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("risks.id", ondelete="SET NULL"), nullable=True
    )
    control_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("controls.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[IssueStatus] = mapped_column(
        Enum(IssueStatus, name="issue_status"), default=IssueStatus.OPEN, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
