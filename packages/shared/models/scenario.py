"""Scenario analysis (Milestone 7): a named what-if narrative linking one
or more risks, used as the target of a portfolio Monte Carlo run.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.shared.db import Base
from packages.shared.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Scenario(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "scenarios"

    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assumptions: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_days: Mapped[int | None] = mapped_column(nullable=True)
    financial_impact_min: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    financial_impact_most_likely: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    financial_impact_max: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    operational_impact: Mapped[str | None] = mapped_column(Text, nullable=True)
    recovery_assumptions: Mapped[str | None] = mapped_column(Text, nullable=True)

    scenario_risks: Mapped[list["ScenarioRisk"]] = relationship(back_populates="scenario")


class ScenarioRisk(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "scenario_risks"
    __table_args__ = (UniqueConstraint("scenario_id", "risk_id", name="uq_scenario_risk"),)

    scenario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False
    )
    risk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("risks.id", ondelete="CASCADE"), nullable=False
    )

    scenario: Mapped[Scenario] = relationship(back_populates="scenario_risks")
