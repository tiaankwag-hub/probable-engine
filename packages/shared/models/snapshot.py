from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.shared.db import Base
from packages.shared.models.base import UUIDPrimaryKeyMixin


class Snapshot(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "snapshots"

    label: Mapped[str] = mapped_column(String(200), nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    snapshot_risks: Mapped[list["SnapshotRisk"]] = relationship(back_populates="snapshot")


class SnapshotRisk(Base, UUIDPrimaryKeyMixin):
    """One frozen row per risk captured at `snapshot.period_end`. `frozen_state`
    mirrors risk_service.serialize_risk_state plus an appetite_status, so
    "What Changed?" (packages/shared/snapshot_service.py) can diff it
    against the live risks table without re-deriving anything."""

    __tablename__ = "snapshot_risks"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("snapshots.id", ondelete="CASCADE"), nullable=False
    )
    risk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("risks.id", ondelete="CASCADE"), nullable=False
    )
    frozen_state: Mapped[dict] = mapped_column(JSONB, nullable=False)

    snapshot: Mapped[Snapshot] = relationship(back_populates="snapshot_risks")
