"""Local-development side of the JobQueue abstraction (ADR 0005): polls the
`background_jobs` table with `SELECT ... FOR UPDATE SKIP LOCKED` so multiple
worker instances can run concurrently without double-processing a job. In
production this process (and this polling loop) does not exist — Cloud Run
receives Cloud Tasks pushes directly instead; only the job *handlers*
(apps/worker/app/jobs/*) are reused as-is.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone

from sqlalchemy import select

from apps.worker.app.jobs import import_commit, report_generate
from packages.shared.db import get_session_factory
from packages.shared.logging import configure_logging, job_id_var
from packages.shared.models.jobs import BackgroundJob, JobStatus
from packages.shared.storage import LocalFileSystemStore

configure_logging()
logger = logging.getLogger("worker")

JOB_HANDLERS = {
    "import_commit": import_commit.handle,
    "report_generate": report_generate.handle,
}

POLL_INTERVAL_SECONDS = float(os.environ.get("WORKER_POLL_INTERVAL_SECONDS", "2"))


def process_one() -> bool:
    """Claims and runs a single pending job. Returns True if a job was
    processed (whether it succeeded or failed), False if the queue was
    empty."""
    session = get_session_factory()()
    object_store = LocalFileSystemStore(os.environ.get("STORAGE_ROOT", "./.data/storage"))
    try:
        job = session.scalars(
            select(BackgroundJob)
            .where(BackgroundJob.status == JobStatus.PENDING)
            .order_by(BackgroundJob.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        ).first()
        if job is None:
            return False

        job.status = JobStatus.RUNNING
        job.updated_at = datetime.now(timezone.utc)
        session.commit()

        token = job_id_var.set(str(job.id))
        try:
            handler = JOB_HANDLERS.get(job.job_type)
            try:
                if handler is None:
                    raise ValueError(f"no handler registered for job_type={job.job_type}")
                handler(session, job.payload, object_store)
                job.status = JobStatus.SUCCEEDED
                job.error = None
                logger.info("job %s (%s) succeeded", job.id, job.job_type)
            except Exception as exc:  # noqa: BLE001 - a job failure must not crash the poller
                session.rollback()
                job = session.get(BackgroundJob, job.id)
                job.status = JobStatus.FAILED
                job.error = str(exc)
                logger.exception("job %s (%s) failed", job.id, job.job_type)
            job.updated_at = datetime.now(timezone.utc)
            session.commit()
            return True
        finally:
            job_id_var.reset(token)
    finally:
        session.close()


def run_forever() -> None:
    logger.info("worker starting, polling every %ss", POLL_INTERVAL_SECONDS)
    while True:
        processed = process_one()
        if not processed:
            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_forever()
