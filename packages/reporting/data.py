"""Report content assembly: reuses the same aggregation
`packages/shared/dashboard_service.py` already computes for the Executive
Dashboard, since a report is just that same data rendered to a file
instead of a browser page.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from packages.shared.dashboard_service import compute_executive_dashboard


@dataclass
class ReportContext:
    generated_at: datetime
    period_start: date | None
    period_end: date | None
    scope_label: str
    dashboard: dict[str, Any]


def build_report_context(
    session: Session,
    *,
    period_start: date | None = None,
    period_end: date | None = None,
    scope: dict[str, Any] | None = None,
) -> ReportContext:
    scope = scope or {}
    return ReportContext(
        generated_at=datetime.now(timezone.utc),
        period_start=period_start,
        period_end=period_end,
        scope_label=scope.get("label") or "All risks",
        dashboard=compute_executive_dashboard(session),
    )
