from __future__ import annotations

import uuid

from pydantic import BaseModel


class WeakControlSummary(BaseModel):
    id: uuid.UUID
    control_code: str
    name: str
    operating_effectiveness: int | None
    design_effectiveness: int | None


class OverdueActionSummary(BaseModel):
    id: uuid.UUID
    action_code: str
    title: str
    due_date: str | None
    owner_email: str | None
    risk_id: uuid.UUID | None


class BreachRiskSummary(BaseModel):
    id: uuid.UUID
    risk_code: str
    title: str
    residual_band: str | None
    appetite_status: str


class GovernanceHealth(BaseModel):
    weak_controls_count: int
    weak_controls: list[WeakControlSummary]
    overdue_actions_count: int
    overdue_actions: list[OverdueActionSummary]
    overdue_reviews_count: int
    appetite_status_counts: dict[str, int]
    breach_risks: list[BreachRiskSummary]
