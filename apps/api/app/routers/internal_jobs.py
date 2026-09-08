"""Endpoints for Cloud Scheduler, not humans (Milestone 11). This router
carries no RBAC dependency and no bearer-token check of any kind — that is
deliberate, not an oversight. Its safety comes entirely from the
surrounding platform, the same way it does for every other route on this
service:

  - `apps/api`'s Cloud Run ingress is never public in this architecture
    (see docs/architecture/01-target-architecture.md's "No public
    production API" principle) — it is reachable only from other Cloud Run
    services on the project's network, never the internet directly.
  - The Cloud Run service additionally requires IAM authentication
    (no `--allow-unauthenticated`), so a request only reaches this code at
    all once Cloud Run's platform has already verified an OIDC token from
    an identity holding `roles/run.invoker` on this specific service.
  - Cloud Scheduler is configured (see infra/modules/scheduler_job and the
    deployment runbook) to call these routes using exactly that mechanism:
    an OIDC token minted for a dedicated, least-privilege service account
    that holds `run.invoker` here and nothing else.

Adding an app-level secret/header check on top would duplicate a check
already enforced, unforgeably, one layer down — and give a false sense
that this router is what's holding the door shut. It isn't; the platform
is. If that ever changes (this service's ingress becomes public, or an
unauthenticated Cloud Run policy is applied), these two routes must move
behind real authentication before that happens, not after.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from apps.api.app.deps import get_db
from packages.shared.models.jobs import BackgroundJob, JobStatus
from packages.shared.snapshot_service import capture_snapshot

router = APIRouter(prefix="/internal/jobs", tags=["internal"])

SCHEDULED_JOB_ACTOR = "scheduler@system"


@router.post("/ingest-emerging-signals", status_code=status.HTTP_202_ACCEPTED)
def ingest_emerging_signals(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    job = BackgroundJob(
        job_type="emerging_signal_ingest", payload={}, status=JobStatus.PENDING,
        created_at=now, updated_at=now,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return {"job_id": str(job.id)}


@router.post("/capture-snapshot", status_code=status.HTTP_201_CREATED)
def capture_scheduled_snapshot(db: Session = Depends(get_db)):
    today = date.today()
    snapshot = capture_snapshot(
        db,
        label=f"Scheduled snapshot {today.isoformat()}",
        period_end=today,
        actor_email=SCHEDULED_JOB_ACTOR,
    )
    db.commit()
    return {"snapshot_id": str(snapshot.id)}
