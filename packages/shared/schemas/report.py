from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from packages.shared.models.report import ReportRunStatus, ReportType


class ReportRequest(BaseModel):
    period_start: date | None = None
    period_end: date | None = None
    scope: dict[str, Any] = Field(default_factory=dict)


class PowerPointReportRequest(ReportRequest):
    template: Literal["one_slide", "two_slide_elt"] = "one_slide"


class ReportRunOut(BaseModel):
    id: uuid.UUID
    report_type: ReportType
    status: ReportRunStatus
    period_start: date | None
    period_end: date | None
    scope: dict[str, Any]
    error: str | None
    created_at: datetime
    generated_at: datetime | None
    download_url: str | None
