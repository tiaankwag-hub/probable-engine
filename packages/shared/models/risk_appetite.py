from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.shared.db import Base
from packages.shared.models.base import UUIDPrimaryKeyMixin


class RiskAppetite(Base, UUIDPrimaryKeyMixin):
    """Schema only in Milestone 1 — evaluation logic (within/approaching/outside/
    material breach) is implemented in Milestone 3 per the roadmap."""

    __tablename__ = "risk_appetite"

    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("risk_categories.id"), nullable=True
    )
    business_unit: Mapped[str | None] = mapped_column(String(200), nullable=True)
    appetite_band: Mapped[str] = mapped_column(String(50), nullable=False)
    tolerance_band: Mapped[str] = mapped_column(String(50), nullable=False)
    limit_value: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
