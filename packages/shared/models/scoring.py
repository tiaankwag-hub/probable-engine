from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.shared.db import Base
from packages.shared.models.base import UUIDPrimaryKeyMixin


class ScoringConfig(Base, UUIDPrimaryKeyMixin):
    """Versioned, database-held scoring configuration (ADR 0007).

    `config` holds impact-dimension weights, band thresholds, and the
    control-effectiveness reduction formula parameters as JSON so thresholds
    can change without a code deployment. Every risk_assessments row records
    the `version` in effect when it was computed.
    """

    __tablename__ = "scoring_config"

    version: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
