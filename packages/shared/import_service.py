"""Import Wizard commit logic (ADR 0008). Runs inside apps/worker (dispatched
via the JobQueue abstraction, ADR 0005) so a large file never blocks an HTTP
request. Reuses `packages.shared.risk_service` so an imported risk is created
through exactly the same scoring/versioning/audit path as one entered by
hand in the UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.shared.audit import record_audit_event
from packages.shared.importing.mapping import ColumnMappingSpec, build_import_rows
from packages.shared.importing.parser import parse_rows
from packages.shared.importing.validation import has_blocking_errors, validate_rows
from packages.shared.models.identity import User
from packages.shared.models.imports import (
    ImportColumnMapping,
    ImportJob,
    ImportJobStatus,
    ImportRowError,
)
from packages.shared.models.risk import Risk, RiskCategory
from packages.shared.risk_service import AssessmentInput, RiskFields, create_risk
from packages.shared.storage import ObjectStore

KNOWN_STATUSES = {"draft", "open", "monitoring", "closed"}
KNOWN_DECISIONS = {"accept", "treat", "transfer", "avoid", "pending"}


class ImportJobNotFound(Exception):
    pass


class ImportHasBlockingErrors(Exception):
    pass


@dataclass
class ImportCommitSummary:
    created: int
    skipped_existing_risk_code: int
    skipped_invalid: int


def get_or_create_category(session: Session, name: str | None) -> RiskCategory | None:
    if not name:
        return None
    existing = session.scalars(select(RiskCategory).where(RiskCategory.name == name)).first()
    if existing:
        return existing
    category = RiskCategory(name=name)
    session.add(category)
    session.flush()
    return category


def find_owner(session: Session, email: str | None) -> User | None:
    if not email:
        return None
    return session.scalars(select(User).where(User.email == email)).first()


def row_to_inputs(mapped: dict, *, category_id, owner_id) -> tuple[RiskFields, AssessmentInput]:
    status_raw = (mapped.get("status_raw") or "").strip().lower()
    decision_raw = (mapped.get("decision_raw") or "").strip().lower()
    fields = RiskFields(
        title=mapped.get("title") or "(untitled)",
        statement=mapped.get("statement"),
        cause=mapped.get("cause"),
        event=mapped.get("event"),
        impact=mapped.get("impact"),
        category_id=category_id,
        business_process=mapped.get("business_process"),
        department=mapped.get("department"),
        owner_id=owner_id,
        status=status_raw if status_raw in KNOWN_STATUSES else "draft",
        decision=decision_raw if decision_raw in KNOWN_DECISIONS else "pending",
        acceptance_rationale=mapped.get("acceptance_rationale"),
        raised_date=mapped.get("raised_date"),
        next_review_date=mapped.get("next_review_date"),
        velocity=mapped.get("velocity"),
        confidence=mapped.get("confidence"),
        treatment_summary=mapped.get("treatment_summary"),
        latest_update=mapped.get("latest_update"),
    )
    assessment = AssessmentInput(
        likelihood=mapped["likelihood"],
        impact_financial=mapped["impact_financial"],
        impact_customer_service=mapped["impact_customer_service"],
        impact_operational_delivery=mapped["impact_operational_delivery"],
        impact_legal_regulatory=mapped["impact_legal_regulatory"],
        impact_reputation=mapped["impact_reputation"],
        impact_health_safety=mapped["impact_health_safety"],
        control_effectiveness=mapped.get("control_effectiveness"),
    )
    return fields, assessment


def commit_import_job(
    session: Session, *, import_job_id, object_store: ObjectStore, actor_email: str
) -> ImportCommitSummary:
    import_job = session.get(ImportJob, import_job_id)
    if import_job is None:
        raise ImportJobNotFound(str(import_job_id))

    mapping_rows = session.scalars(
        select(ImportColumnMapping).where(ImportColumnMapping.import_job_id == import_job_id)
    ).all()
    mappings = [
        ColumnMappingSpec(m.source_column, m.domain_field, m.transform) for m in mapping_rows
    ]

    file_path = object_store.get(import_job.storage_key)
    raw_rows = parse_rows(file_path)
    import_rows = build_import_rows(raw_rows, mappings)

    known_categories = {c.name for c in session.scalars(select(RiskCategory)).all()}
    known_emails = {u.email for u in session.scalars(select(User)).all()}
    issues = validate_rows(
        import_rows, known_category_names=known_categories, known_owner_emails=known_emails
    )

    session.query(ImportRowError).filter(
        ImportRowError.import_job_id == import_job_id
    ).delete()
    for issue in issues:
        session.add(
            ImportRowError(
                import_job_id=import_job_id,
                row_number=issue.row_number,
                field=issue.field,
                error_type=issue.error_type,
                raw_value=str(issue.raw_value) if issue.raw_value is not None else None,
            )
        )

    if has_blocking_errors(issues):
        import_job.status = ImportJobStatus.FAILED
        import_job.updated_at = datetime.now(timezone.utc)
        raise ImportHasBlockingErrors(f"{len(issues)} validation issue(s) found")

    errors_by_row: dict[int, list] = {}
    for issue in issues:
        errors_by_row.setdefault(issue.row_number, []).append(issue)

    created = 0
    skipped_existing = 0
    skipped_invalid = 0

    for row in import_rows:
        if errors_by_row.get(row.row_number):
            skipped_invalid += 1
            continue

        existing = session.scalars(
            select(Risk).where(Risk.risk_code == row.mapped.get("risk_code"))
        ).first()
        if existing is not None:
            skipped_existing += 1
            session.add(
                ImportRowError(
                    import_job_id=import_job_id,
                    row_number=row.row_number,
                    field="risk_code",
                    error_type="existing_risk_conflict",
                    raw_value=row.mapped.get("risk_code"),
                )
            )
            continue

        category = get_or_create_category(session, row.mapped.get("category_name"))
        owner = find_owner(session, row.mapped.get("owner_email"))
        fields, assessment = row_to_inputs(
            row.mapped,
            category_id=category.id if category else None,
            owner_id=owner.id if owner else None,
        )
        create_risk(
            session,
            fields=fields,
            assessment_input=assessment,
            actor_email=actor_email,
            actor_id=None,
            source="import",
            risk_code=row.mapped.get("risk_code"),
        )
        created += 1

    import_job.status = ImportJobStatus.COMMITTED
    import_job.updated_at = datetime.now(timezone.utc)
    summary = ImportCommitSummary(
        created=created, skipped_existing_risk_code=skipped_existing, skipped_invalid=skipped_invalid
    )
    record_audit_event(
        session,
        actor=actor_email,
        entity="import_job",
        entity_id=import_job_id,
        action="commit",
        old_value=None,
        new_value={
            "created": created,
            "skipped_existing_risk_code": skipped_existing,
            "skipped_invalid": skipped_invalid,
        },
        source="import",
    )
    return summary
