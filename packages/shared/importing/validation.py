"""Validates mapped import rows before they can be previewed/committed.

Errors block commit; warnings are surfaced to the user but do not. Nothing
here silently drops or coerces a bad value — every problem produces an
`ImportRowError`-shaped issue the user reviews in the wizard (brief's "show
issues" step), consistent with the "never silently overwrite" principle
extended to "never silently drop".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from packages.shared.importing.mapping import IMPACT_FIELDS, ImportRow

Severity = Literal["error", "warning"]

KNOWN_STATUSES = {"draft", "open", "monitoring", "closed"}
KNOWN_DECISIONS = {"accept", "treat", "transfer", "avoid", "pending"}


@dataclass(frozen=True)
class ValidationIssue:
    row_number: int
    field: str | None
    error_type: str
    message: str
    severity: Severity
    raw_value: Any = None


def _issue(
    row: ImportRow, field: str | None, error_type: str, message: str, severity: Severity
) -> ValidationIssue:
    raw_value = row.raw.get(field) if field else None
    return ValidationIssue(
        row_number=row.row_number,
        field=field,
        error_type=error_type,
        message=message,
        severity=severity,
        raw_value=raw_value,
    )


def validate_rows(
    rows: list[ImportRow],
    *,
    known_category_names: set[str] | None = None,
    known_owner_emails: set[str] | None = None,
) -> list[ValidationIssue]:
    known_category_names = known_category_names or set()
    known_owner_emails = known_owner_emails or set()
    issues: list[ValidationIssue] = []
    seen_risk_codes: dict[str, int] = {}

    for row in rows:
        risk_code = row.mapped.get("risk_code")
        if not risk_code:
            issues.append(
                _issue(row, "risk_code", "missing_required_field", "risk_code is required", "error")
            )
        elif risk_code in seen_risk_codes:
            issues.append(
                _issue(
                    row,
                    "risk_code",
                    "duplicate_risk_code",
                    f"risk_code '{risk_code}' also appears on row {seen_risk_codes[risk_code]}",
                    "error",
                )
            )
        else:
            seen_risk_codes[risk_code] = row.row_number

        if not row.mapped.get("title"):
            issues.append(
                _issue(row, "title", "missing_required_field", "title is required", "error")
            )

        likelihood = row.mapped.get("likelihood")
        if likelihood is None:
            issues.append(
                _issue(
                    row,
                    "likelihood_1_5_12_month_horizon",
                    "invalid_scale_value",
                    "likelihood must be an integer between 1 and 5",
                    "error",
                )
            )

        for field in IMPACT_FIELDS:
            if row.mapped.get(field) is None:
                issues.append(
                    _issue(
                        row, field, "invalid_scale_value",
                        f"{field} must be an integer between 1 and 5", "error",
                    )
                )

        category_name = row.mapped.get("category_name")
        if category_name and category_name not in known_category_names:
            issues.append(
                _issue(
                    row, "category_name", "unknown_category",
                    f"category '{category_name}' does not exist yet and will be created", "warning",
                )
            )

        owner_email = row.mapped.get("owner_email")
        if owner_email and owner_email not in known_owner_emails:
            issues.append(
                _issue(
                    row, "owner_email", "unknown_owner",
                    f"owner '{owner_email}' does not match a known user; "
                    "risk will be imported unassigned", "warning",
                )
            )

        status_raw = (row.mapped.get("status_raw") or "").strip().lower()
        if status_raw and status_raw not in KNOWN_STATUSES:
            issues.append(
                _issue(
                    row, "status_raw", "unrecognized_enum_value",
                    f"status '{status_raw}' not recognized; will default to 'draft'", "warning",
                )
            )

        decision_raw = (row.mapped.get("decision_raw") or "").strip().lower()
        if decision_raw and decision_raw not in KNOWN_DECISIONS:
            issues.append(
                _issue(
                    row, "decision_raw", "unrecognized_enum_value",
                    f"decision '{decision_raw}' not recognized; will default to 'pending'", "warning",
                )
            )

        if decision_raw == "accept" and not row.mapped.get("acceptance_rationale"):
            issues.append(
                _issue(
                    row, "acceptance_rationale", "missing_required_field",
                    "acceptance_rationale is required when decision is 'accept'", "error",
                )
            )

    return issues


def has_blocking_errors(issues: list[ValidationIssue]) -> bool:
    return any(issue.severity == "error" for issue in issues)
