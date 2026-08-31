"""Ingests new signals from every configured adapter and triages each
newly-created one against the active AI provider (Milestone 9, ADR 0005).
No dedicated "ingestion run" entity exists in the domain model — this
job's outcome is observable through the `emerging_signals`/
`emerging_risk_candidates` rows it writes, and its own progress through
the generic `BackgroundJob` status `apps/api/app/routers/jobs.py` already
exposes for polling (`GET /api/v1/jobs/{id}`).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from packages.ai.factory import get_provider
from packages.shared.emerging_risk_service import ingest_signals, triage_signal
from packages.shared.storage import ObjectStore


def handle(session: Session, _payload: dict, _object_store: ObjectStore) -> None:
    new_signals = ingest_signals(session)
    session.commit()

    provider = get_provider()
    for signal in new_signals:
        triage_signal(session, provider, signal)
        session.commit()
