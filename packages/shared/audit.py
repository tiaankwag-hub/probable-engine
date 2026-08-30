"""Immutable audit event writer (ADR 0012).

`record_audit_event` is the *only* sanctioned way to write to `audit_events`
— it never updates or deletes an existing row. Call it inside the same
transaction as the authoritative change it describes so the two commit or
roll back together.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from packages.shared.models.audit import AuditEvent


def record_audit_event(
    session: Session,
    *,
    actor: str,
    entity: str,
    entity_id: uuid.UUID,
    action: str,
    old_value: dict[str, Any] | None,
    new_value: dict[str, Any] | None,
    source: str,
    reason: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor=actor,
        occurred_at=datetime.now(timezone.utc),
        entity=entity,
        entity_id=entity_id,
        action=action,
        old_value=old_value,
        new_value=new_value,
        reason=reason,
        source=source,
    )
    session.add(event)
    return event
