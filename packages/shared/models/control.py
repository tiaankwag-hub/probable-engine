from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.shared.db import Base
from packages.shared.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class ControlType(str, enum.Enum):
    PREVENTIVE = "preventive"
    DETECTIVE = "detective"
    CORRECTIVE = "corrective"


class ControlAutomation(str, enum.Enum):
    MANUAL = "manual"
    AUTOMATED = "automated"


class ControlStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"


class ControlTestResult(str, enum.Enum):
    EFFECTIVE = "effective"
    PARTIALLY_EFFECTIVE = "partially_effective"
    INEFFECTIVE = "ineffective"
    NOT_TESTED = "not_tested"


class Control(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "controls"

    control_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    control_type: Mapped[ControlType] = mapped_column(Enum(ControlType, name="control_type"), nullable=False)
    automation: Mapped[ControlAutomation] = mapped_column(
        Enum(ControlAutomation, name="control_automation"), nullable=False
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    frequency: Mapped[str | None] = mapped_column(String(100), nullable=True)
    design_effectiveness: Mapped[int | None] = mapped_column(Integer, nullable=True)
    operating_effectiveness: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_tested: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_test: Mapped[date | None] = mapped_column(Date, nullable=True)
    evidence: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[ControlStatus] = mapped_column(
        Enum(ControlStatus, name="control_status"), default=ControlStatus.DRAFT, nullable=False
    )

    tests: Mapped[list["ControlTest"]] = relationship(
        back_populates="control", order_by="ControlTest.test_date.desc()"
    )


class RiskControl(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "risk_controls"
    __table_args__ = (UniqueConstraint("risk_id", "control_id", name="uq_risk_control"),)

    risk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("risks.id", ondelete="CASCADE"), nullable=False
    )
    control_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("controls.id", ondelete="CASCADE"), nullable=False
    )


class ControlTest(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "control_tests"

    control_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("controls.id", ondelete="CASCADE"), nullable=False
    )
    tester: Mapped[str] = mapped_column(String(300), nullable=False)
    test_date: Mapped[date] = mapped_column(Date, nullable=False)
    test_method: Mapped[str | None] = mapped_column(String(300), nullable=True)
    result: Mapped[ControlTestResult] = mapped_column(
        Enum(ControlTestResult, name="control_test_result"), nullable=False
    )
    evidence: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    finding: Mapped[str | None] = mapped_column(Text, nullable=True)
    remediation_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    control: Mapped[Control] = relationship(back_populates="tests")
