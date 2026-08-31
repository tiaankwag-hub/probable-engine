"""Reporting (Milestone 5). Report *templates* are fixed code
(`packages/reporting`), not admin-managed data — the domain model's
`reports`/`report_runs` split is simplified to a single `ReportRun` row
carrying `report_type` directly, since the API design's actual endpoints
(`POST /reports/pdf`, `POST /reports/powerpoint`) never call for a
template-management CRUD. `ReportRun` is the audit trail of who generated
what, over what scope, and where the resulting file landed in object
storage.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.shared.db import Base
from packages.shared.models.base import UUIDPrimaryKeyMixin


class ReportType(str, enum.Enum):
    PDF_EXECUTIVE_SUMMARY = "pdf_executive_summary"
    PPTX_ONE_SLIDE = "pptx_one_slide"
    PPTX_TWO_SLIDE_ELT = "pptx_two_slide_elt"


class ReportRunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ReportRun(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "report_runs"

    report_type: Mapped[ReportType] = mapped_column(
        Enum(ReportType, name="report_type"), nullable=False
    )
    requested_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    scope: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[ReportRunStatus] = mapped_column(
        Enum(ReportRunStatus, name="report_run_status"),
        default=ReportRunStatus.PENDING,
        nullable=False,
    )
    generated_file_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
