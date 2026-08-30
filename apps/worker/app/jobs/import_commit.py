from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from packages.shared.import_service import commit_import_job
from packages.shared.storage import ObjectStore


def handle(session: Session, payload: dict, object_store: ObjectStore) -> None:
    commit_import_job(
        session,
        import_job_id=uuid.UUID(payload["import_job_id"]),
        object_store=object_store,
        actor_email=payload.get("actor_email", "worker@system"),
    )
