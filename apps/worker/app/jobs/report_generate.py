from __future__ import annotations

import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from packages.reporting import (
    build_report_context,
    render_pdf_executive_summary,
    render_pptx_one_slide,
    render_pptx_two_slide_elt,
)
from packages.shared.models.report import ReportRun, ReportRunStatus, ReportType
from packages.shared.storage import ObjectStore

RENDERERS = {
    ReportType.PDF_EXECUTIVE_SUMMARY: (render_pdf_executive_summary, "pdf"),
    ReportType.PPTX_ONE_SLIDE: (render_pptx_one_slide, "pptx"),
    ReportType.PPTX_TWO_SLIDE_ELT: (render_pptx_two_slide_elt, "pptx"),
}


def handle(session: Session, payload: dict, object_store: ObjectStore) -> None:
    run = session.get(ReportRun, uuid.UUID(payload["report_run_id"]))
    if run is None:
        raise ValueError(f"report run not found: {payload['report_run_id']}")

    run.status = ReportRunStatus.RUNNING
    run.updated_at = datetime.now(timezone.utc)
    session.commit()

    try:
        renderer, extension = RENDERERS[run.report_type]
        context = build_report_context(
            session, period_start=run.period_start, period_end=run.period_end, scope=run.scope
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / f"report.{extension}"
            renderer(context, output_path)
            file_key = object_store.put(output_path, key=f"reports/{run.id}.{extension}")
    except Exception as exc:  # noqa: BLE001 - surfaced on the run so the Reports page shows it
        run.status = ReportRunStatus.FAILED
        run.error = str(exc)
        run.updated_at = datetime.now(timezone.utc)
        session.commit()
        raise

    run.status = ReportRunStatus.SUCCEEDED
    run.generated_file_key = file_key
    run.generated_at = datetime.now(timezone.utc)
    run.updated_at = datetime.now(timezone.utc)
    session.commit()
