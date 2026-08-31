from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class SnapshotCreate(BaseModel):
    label: str
    period_end: date | None = None


class SnapshotOut(BaseModel):
    id: uuid.UUID
    label: str
    period_end: date
    created_at: datetime
    risk_count: int


class ChangedRisk(BaseModel):
    id: uuid.UUID
    risk_code: str
    title: str
    from_band: str | None = None
    to_band: str | None = None
    from_owner_id: str | None = None
    to_owner_id: str | None = None
    from_status: str | None = None
    to_status: str | None = None


class WhatChanged(BaseModel):
    since_snapshot_id: uuid.UUID
    since_label: str
    since_period_end: str
    new_risks: list[ChangedRisk]
    closed_risks: list[ChangedRisk]
    escalated_risks: list[ChangedRisk]
    downgraded_risks: list[ChangedRisk]
    owner_changes: list[ChangedRisk]
    appetite_changes: list[ChangedRisk]


class TrendPoint(BaseModel):
    label: str
    period_end: str
    total_risks: int
    low: int
    moderate: int
    high: int
    extreme: int
