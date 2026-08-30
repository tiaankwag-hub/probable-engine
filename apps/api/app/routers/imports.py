"""Import Wizard endpoints (ADR 0008): upload -> inspect columns -> map ->
validate -> preview -> commit. Everything except the initial upload and
column inspection is bounded by "one uploaded file's rows", but commit is
still dispatched to apps/worker via the JobQueue table (ADR 0005) rather
than run inline, since row counts are not bounded in general.
"""

from __future__ import annotations

import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.deps import CurrentUser, get_db, get_object_store, require_permission
from packages.shared.audit import record_audit_event
from packages.shared.importing.mapping import (
    DEFAULT_RISK_REGISTER_MAPPING,
    ColumnMappingSpec,
    build_import_rows,
)
from packages.shared.importing.parser import parse_columns, parse_rows
from packages.shared.importing.validation import validate_rows
from packages.shared.models.identity import User
from packages.shared.models.imports import (
    ImportColumnMapping,
    ImportJob,
    ImportJobStatus,
    ImportRowError,
)
from packages.shared.models.jobs import BackgroundJob, JobStatus
from packages.shared.models.risk import RiskCategory
from packages.shared.rbac import RUN_IMPORTS
from packages.shared.schemas.imports import (
    ColumnMappingEntry,
    ColumnsOut,
    CommitResultOut,
    ImportJobOut,
    PreviewOut,
    PreviewRowOut,
    SetMappingIn,
    ValidationIssueOut,
    ValidationResultOut,
)
from packages.shared.storage import ObjectStore

router = APIRouter(prefix="/api/v1/imports", tags=["imports"])

_DEFAULT_MAPPING_BY_COLUMN = {m.source_column: m for m in DEFAULT_RISK_REGISTER_MAPPING}


def _get_job_or_404(db: Session, import_job_id: uuid.UUID) -> ImportJob:
    job = db.get(ImportJob, import_job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="import job not found")
    return job


def _load_mappings(db: Session, import_job_id: uuid.UUID) -> list[ColumnMappingSpec]:
    rows = db.scalars(
        select(ImportColumnMapping).where(ImportColumnMapping.import_job_id == import_job_id)
    ).all()
    return [ColumnMappingSpec(r.source_column, r.domain_field, r.transform) for r in rows]


@router.post("", response_model=ImportJobOut, status_code=status.HTTP_201_CREATED)
def upload_import(
    file: UploadFile,
    db: Session = Depends(get_db),
    store: ObjectStore = Depends(get_object_store),
    current_user: CurrentUser = Depends(require_permission(RUN_IMPORTS)),
):
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="only .xlsx files are supported"
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)
    try:
        key = store.put(tmp_path, key=f"imports/{uuid.uuid4()}.xlsx")
    finally:
        tmp_path.unlink(missing_ok=True)

    now = datetime.now(timezone.utc)
    job = ImportJob(
        filename=file.filename,
        storage_key=key,
        uploaded_by=current_user.user.id,
        status=ImportJobStatus.UPLOADED,
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.get("/{import_job_id}", response_model=ImportJobOut)
def get_import_job(
    import_job_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(RUN_IMPORTS)),
):
    return _get_job_or_404(db, import_job_id)


@router.get("/{import_job_id}/columns", response_model=ColumnsOut)
def inspect_columns(
    import_job_id: uuid.UUID,
    db: Session = Depends(get_db),
    store: ObjectStore = Depends(get_object_store),
    _user: CurrentUser = Depends(require_permission(RUN_IMPORTS)),
):
    job = _get_job_or_404(db, import_job_id)
    file_path = store.get(job.storage_key)
    columns = parse_columns(file_path)
    suggested = [
        ColumnMappingEntry(
            source_column=col,
            domain_field=(_DEFAULT_MAPPING_BY_COLUMN[col].domain_field if col in _DEFAULT_MAPPING_BY_COLUMN else None),
            transform=(_DEFAULT_MAPPING_BY_COLUMN[col].transform if col in _DEFAULT_MAPPING_BY_COLUMN else None),
        )
        for col in columns
    ]
    return ColumnsOut(columns=columns, suggested_mapping=suggested)


@router.put("/{import_job_id}/mapping", response_model=ImportJobOut)
def set_mapping(
    import_job_id: uuid.UUID,
    payload: SetMappingIn,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(RUN_IMPORTS)),
):
    job = _get_job_or_404(db, import_job_id)

    db.query(ImportColumnMapping).filter(
        ImportColumnMapping.import_job_id == import_job_id
    ).delete()
    for entry in payload.mappings:
        db.add(
            ImportColumnMapping(
                import_job_id=import_job_id,
                source_column=entry.source_column,
                domain_field=entry.domain_field,
                transform=entry.transform,
            )
        )
    job.status = ImportJobStatus.MAPPED
    job.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job


@router.post("/{import_job_id}/validate", response_model=ValidationResultOut)
def validate_import(
    import_job_id: uuid.UUID,
    db: Session = Depends(get_db),
    store: ObjectStore = Depends(get_object_store),
    _user: CurrentUser = Depends(require_permission(RUN_IMPORTS)),
):
    job = _get_job_or_404(db, import_job_id)
    mappings = _load_mappings(db, import_job_id)
    if not mappings:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="set a column mapping before validating",
        )

    file_path = store.get(job.storage_key)
    raw_rows = parse_rows(file_path)
    import_rows = build_import_rows(raw_rows, mappings)

    known_categories = {c.name for c in db.scalars(select(RiskCategory)).all()}
    known_emails = {u.email for u in db.scalars(select(User)).all()}
    issues = validate_rows(
        import_rows, known_category_names=known_categories, known_owner_emails=known_emails
    )

    db.query(ImportRowError).filter(ImportRowError.import_job_id == import_job_id).delete()
    for issue in issues:
        db.add(
            ImportRowError(
                import_job_id=import_job_id,
                row_number=issue.row_number,
                field=issue.field,
                error_type=issue.error_type,
                raw_value=str(issue.raw_value) if issue.raw_value is not None else None,
            )
        )
    job.status = ImportJobStatus.VALIDATED
    job.updated_at = datetime.now(timezone.utc)
    db.commit()

    blocking = sum(1 for i in issues if i.severity == "error")
    return ValidationResultOut(
        issue_count=len(issues),
        blocking_error_count=blocking,
        issues=[ValidationIssueOut(**vars(i)) for i in issues],
    )


@router.get("/{import_job_id}/preview", response_model=PreviewOut)
def preview_import(
    import_job_id: uuid.UUID,
    db: Session = Depends(get_db),
    store: ObjectStore = Depends(get_object_store),
    _user: CurrentUser = Depends(require_permission(RUN_IMPORTS)),
    limit: int = 50,
):
    job = _get_job_or_404(db, import_job_id)
    mappings = _load_mappings(db, import_job_id)
    file_path = store.get(job.storage_key)
    raw_rows = parse_rows(file_path)
    import_rows = build_import_rows(raw_rows, mappings)

    known_categories = {c.name for c in db.scalars(select(RiskCategory)).all()}
    known_emails = {u.email for u in db.scalars(select(User)).all()}
    issues = validate_rows(
        import_rows, known_category_names=known_categories, known_owner_emails=known_emails
    )
    issues_by_row: dict[int, list] = {}
    for issue in issues:
        issues_by_row.setdefault(issue.row_number, []).append(issue)

    preview_rows = [
        PreviewRowOut(
            row_number=row.row_number,
            mapped={k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in row.mapped.items()},
            issues=[ValidationIssueOut(**vars(i)) for i in issues_by_row.get(row.row_number, [])],
        )
        for row in import_rows[:limit]
    ]
    return PreviewOut(total_rows=len(import_rows), rows=preview_rows)


@router.post("/{import_job_id}/commit", response_model=CommitResultOut, status_code=status.HTTP_202_ACCEPTED)
def commit_import(
    import_job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(RUN_IMPORTS)),
):
    job = _get_job_or_404(db, import_job_id)
    if job.status not in (ImportJobStatus.VALIDATED, ImportJobStatus.PREVIEWED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="run /validate before committing",
        )

    now = datetime.now(timezone.utc)
    job.status = ImportJobStatus.COMMITTING
    job.updated_at = now

    background_job = BackgroundJob(
        job_type="import_commit",
        payload={"import_job_id": str(import_job_id), "actor_email": current_user.email},
        status=JobStatus.PENDING,
        created_at=now,
        updated_at=now,
    )
    db.add(background_job)
    record_audit_event(
        db,
        actor=current_user.email,
        entity="import_job",
        entity_id=import_job_id,
        action="commit_requested",
        old_value=None,
        new_value={"background_job_id": str(background_job.id)},
        source="ui",
    )
    db.commit()
    db.refresh(background_job)

    return CommitResultOut(
        job_id=import_job_id, background_job_id=background_job.id, status="pending"
    )
