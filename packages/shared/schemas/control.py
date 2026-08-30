from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from packages.shared.models.control import (
    ControlAutomation,
    ControlStatus,
    ControlTestResult,
    ControlType,
)


class ControlIn(BaseModel):
    control_code: str | None = Field(default=None, max_length=50)
    name: str = Field(max_length=300)
    description: str | None = None
    control_type: ControlType
    automation: ControlAutomation
    owner_id: uuid.UUID | None = None
    frequency: str | None = None
    design_effectiveness: int | None = Field(default=None, ge=1, le=5)
    operating_effectiveness: int | None = Field(default=None, ge=1, le=5)
    last_tested: date | None = None
    next_test: date | None = None
    status: ControlStatus = ControlStatus.DRAFT


class ControlOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    control_code: str
    name: str
    description: str | None
    control_type: ControlType
    automation: ControlAutomation
    owner_id: uuid.UUID | None
    frequency: str | None
    design_effectiveness: int | None
    operating_effectiveness: int | None
    last_tested: date | None
    next_test: date | None
    evidence: str | None
    status: ControlStatus
    created_at: datetime
    updated_at: datetime


class ControlTestIn(BaseModel):
    tester: str = Field(max_length=300)
    test_date: date
    test_method: str | None = None
    result: ControlTestResult
    finding: str | None = None
    remediation_action: str | None = None


class ControlTestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    control_id: uuid.UUID
    tester: str
    test_date: date
    test_method: str | None
    result: ControlTestResult
    evidence: str | None
    finding: str | None
    remediation_action: str | None
    created_at: datetime


class LinkControlIn(BaseModel):
    control_id: uuid.UUID
