"""Reports API (Milestone 5): request a PDF or PowerPoint generation
(dispatched to apps/worker via the JobQueue table, same pattern as the
Import Wizard's commit step — rendering is CPU-bound and shouldn't block
a request), poll run status, and download the finished file.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.deps import CurrentUser, get_db, get_object_store, require_permission
from packages.shared.audit import record_audit_event
from packages.shared.models.jobs import BackgroundJob, JobStatus
from packages.shared.models.report import ReportRun, ReportRunStatus, ReportType
from packages.shared.rbac import GENERATE_REPORTS, VIEW_REPORT_RUNS
from packages.shared.schemas.report import PowerPointReportRequest, ReportRequest, ReportRunOut
from packages.shared.storage import ObjectStore

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])

MEDIA_TYPES = {
    ReportType.PDF_EXECUTIVE_SUMMARY: "application/pdf",
    ReportType.PPTX_ONE_SLIDE: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ReportType.PPTX_TWO_SLIDE_ELT: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
FILE_EXTENSIONS = {
    ReportType.PDF_EXECUTIVE_SUMMARY: "pdf",
    ReportType.PPTX_ONE_SLIDE: "pptx",
    ReportType.PPTX_TWO_SLIDE_ELT: "pptx",
}


def _to_out(run: ReportRun) -> ReportRunOut:
    download_url = (
        f"/api/v1/reports/runs/{run.id}/download" if run.status == ReportRunStatus.SUCCEEDED else None
    )
    return ReportRunOut(
        id=run.id,
        report_type=run.report_type,
        status=run.status,
        period_start=run.period_start,
        period_end=run.period_end,
        scope=run.scope,
        error=run.error,
        created_at=run.created_at,
        generated_at=run.generated_at,
        download_url=download_url,
    )


def _create_run(
    db: Session, *, report_type: ReportType, payload: ReportRequest, current_user: CurrentUser
) -> ReportRun:
    now = datetime.now(timezone.utc)
    run = ReportRun(
        report_type=report_type,
        requested_by_id=current_user.user.id,
        period_start=payload.period_start,
        period_end=payload.period_end,
        scope=payload.scope,
        status=ReportRunStatus.PENDING,
        created_at=now,
        updated_at=now,
    )
    db.add(run)
    db.flush()

    background_job = BackgroundJob(
        job_type="report_generate",
        payload={"report_run_id": str(run.id)},
        status=JobStatus.PENDING,
        created_at=now,
        updated_at=now,
    )
    db.add(background_job)
    record_audit_event(
        db,
        actor=current_user.email,
        entity="report_run",
        entity_id=run.id,
        action="requested",
        old_value=None,
        new_value={"report_type": report_type.value, "background_job_id": str(background_job.id)},
        source="ui",
    )
    db.commit()
    db.refresh(run)
    return run


@router.post("/pdf", response_model=ReportRunOut, status_code=status.HTTP_202_ACCEPTED)
def request_pdf_report(
    payload: ReportRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(GENERATE_REPORTS)),
):
    run = _create_run(
        db, report_type=ReportType.PDF_EXECUTIVE_SUMMARY, payload=payload, current_user=current_user
    )
    return _to_out(run)


@router.post("/powerpoint", response_model=ReportRunOut, status_code=status.HTTP_202_ACCEPTED)
def request_powerpoint_report(
    payload: PowerPointReportRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(GENERATE_REPORTS)),
):
    report_type = (
        ReportType.PPTX_TWO_SLIDE_ELT if payload.template == "two_slide_elt" else ReportType.PPTX_ONE_SLIDE
    )
    run = _create_run(db, report_type=report_type, payload=payload, current_user=current_user)
    return _to_out(run)


@router.get("/runs", response_model=list[ReportRunOut])
def list_report_runs(
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(VIEW_REPORT_RUNS)),
):
    runs = db.scalars(select(ReportRun).order_by(ReportRun.created_at.desc())).all()
    return [_to_out(r) for r in runs]


@router.get("/runs/{run_id}", response_model=ReportRunOut)
def get_report_run(
    run_id: uuid.UUID,
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(require_permission(VIEW_REPORT_RUNS)),
):
    run = db.get(ReportRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report run not found")
    return _to_out(run)


@router.get("/runs/{run_id}/download")
def download_report_run(
    run_id: uuid.UUID,
    db: Session = Depends(get_db),
    store: ObjectStore = Depends(get_object_store),
    _user: CurrentUser = Depends(require_permission(VIEW_REPORT_RUNS)),
):
    run = db.get(ReportRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report run not found")
    if run.status != ReportRunStatus.SUCCEEDED or not run.generated_file_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="report is not ready")

    file_path = store.get(run.generated_file_key)
    extension = FILE_EXTENSIONS[run.report_type]
    filename = f"{run.report_type.value}-{run.id}.{extension}"
    return FileResponse(file_path, media_type=MEDIA_TYPES[run.report_type], filename=filename)
