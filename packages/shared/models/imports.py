from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.shared.db import Base
from packages.shared.models.base import UUIDPrimaryKeyMixin


class ImportJobStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    MAPPED = "mapped"
    VALIDATED = "validated"
    PREVIEWED = "previewed"
    COMMITTING = "committing"
    COMMITTED = "committed"
    FAILED = "failed"


class ImportJob(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "import_jobs"

    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1000), nullable=False)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    status: Mapped[ImportJobStatus] = mapped_column(
        Enum(ImportJobStatus, name="import_job_status"),
        default=ImportJobStatus.UPLOADED,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    mappings: Mapped[list["ImportColumnMapping"]] = relationship(back_populates="import_job")
    row_errors: Mapped[list["ImportRowError"]] = relationship(back_populates="import_job")


class ImportColumnMapping(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "import_column_mappings"

    import_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("import_jobs.id", ondelete="CASCADE"), nullable=False
    )
    source_column: Mapped[str] = mapped_column(String(300), nullable=False)
    domain_field: Mapped[str | None] = mapped_column(String(200), nullable=True)
    transform: Mapped[str | None] = mapped_column(String(200), nullable=True)

    import_job: Mapped[ImportJob] = relationship(back_populates="mappings")


class ImportRowError(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "import_row_errors"

    import_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("import_jobs.id", ondelete="CASCADE"), nullable=False
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    field: Mapped[str | None] = mapped_column(String(200), nullable=True)
    error_type: Mapped[str] = mapped_column(String(100), nullable=False)
    raw_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    import_job: Mapped[ImportJob] = relationship(back_populates="row_errors")
