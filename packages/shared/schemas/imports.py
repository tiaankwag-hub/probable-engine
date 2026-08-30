from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from packages.shared.models.imports import ImportJobStatus


class ImportJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    status: ImportJobStatus
    created_at: datetime
    updated_at: datetime


class ColumnsOut(BaseModel):
    columns: list[str]
    suggested_mapping: list["ColumnMappingEntry"]


class ColumnMappingEntry(BaseModel):
    source_column: str
    domain_field: str | None
    transform: str | None = None


class SetMappingIn(BaseModel):
    mappings: list[ColumnMappingEntry]


class ValidationIssueOut(BaseModel):
    row_number: int
    field: str | None
    error_type: str
    message: str
    severity: str
    raw_value: Any = None


class ValidationResultOut(BaseModel):
    issue_count: int
    blocking_error_count: int
    issues: list[ValidationIssueOut]


class PreviewRowOut(BaseModel):
    row_number: int
    mapped: dict[str, Any]
    issues: list[ValidationIssueOut]


class PreviewOut(BaseModel):
    total_rows: int
    rows: list[PreviewRowOut]


class CommitResultOut(BaseModel):
    job_id: uuid.UUID
    background_job_id: uuid.UUID
    status: str
