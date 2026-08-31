"""Monte Carlo simulation (Milestones 6-7).

A `SimulationConfig` belongs to exactly one risk and holds everything
needed to reproduce a run of that risk's frequency-severity model
(`packages.simulations.engine`). A `SimulationRun` executes either one
config (`config_id` set — a single-risk run) or one scenario
(`scenario_id` set — a portfolio run that looks up every linked risk's
own latest config); exactly one of the two is set, enforced in
`packages.shared.simulation_service`, not at the schema level, matching
this codebase's existing pattern of validating "exactly one of A/B" in
the service layer (see Issue/Incident's optional risk_id/control_id).
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.shared.db import Base
from packages.shared.models.base import UUIDPrimaryKeyMixin
from packages.simulations.distributions import DistributionType


class SimulationRunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class SimulationConfig(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "simulation_configs"

    risk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("risks.id", ondelete="CASCADE"), nullable=False
    )
    distribution_type: Mapped[DistributionType] = mapped_column(
        Enum(DistributionType, name="simulation_distribution_type"), nullable=False
    )
    loss_min: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    loss_most_likely: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    loss_max: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    annual_event_frequency: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False, default=1.0)
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    correlation_group: Mapped[str | None] = mapped_column(String(100), nullable=True)
    correlation_strength: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    iterations: Mapped[int] = mapped_column(Integer, nullable=False, default=10_000)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SimulationRun(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "simulation_runs"

    config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("simulation_configs.id", ondelete="CASCADE"), nullable=True
    )
    scenario_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=True
    )
    status: Mapped[SimulationRunStatus] = mapped_column(
        Enum(SimulationRunStatus, name="simulation_run_status"),
        default=SimulationRunStatus.PENDING,
        nullable=False,
    )
    iterations_used: Mapped[int] = mapped_column(Integer, nullable=False)
    seed_used: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SimulationResult(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "simulation_results"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("simulation_runs.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    expected_annual_loss: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    median: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    p75: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    p90: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    p95: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    p99: Mapped[float] = mapped_column(Numeric(16, 2), nullable=False)
    histogram: Mapped[list] = mapped_column(JSONB, nullable=False)
    per_risk_contribution: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
