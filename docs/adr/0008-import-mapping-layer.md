# ADR 0008: Explicit import-mapping layer decoupled from the domain model

## Status
Accepted

## Context
The only current source of risk data is a spreadsheet with an idiosyncratic column schema
(36 columns, some combining multiple concepts like `risk_statement_cause_event_impact`).
Coupling the domain model to that schema would make the platform fragile to future source
changes (a different exporting tool, a second data source, a schema revision) and violates
the brief's explicit requirement that the domain model not depend on spreadsheet column
names. No real sample file was available to validate against during Milestone 0 (see
`docs/architecture/00-current-state-assessment.md`), which reinforces treating the mapping
as configurable rather than assumed.

## Decision
Introduce a staging layer (`import_jobs`, `import_column_mappings`, `import_row_errors`)
and an Import Wizard flow (upload → inspect columns → map → validate → preview → commit →
audit event) as described in `docs/architecture/02-domain-model.md`. Mappings are
data (stored per job, optionally saved as a reusable template), not code. Transformations
(e.g. splitting a combined cause/event/impact field) are named, tested functions selectable
per mapping, not one-off inline parsing.

## Consequences
- A schema change in the source spreadsheet requires re-mapping through the wizard, not a
  code deployment.
- A second future source (a different register, a CSV export from another tool) reuses the
  same wizard and staging tables.
- Commit never silently overwrites an existing risk; a matching `risk_code` produces a
  proposed update requiring explicit confirmation, and always emits an audit event with
  `source = 'import'`.
- Adds up-front complexity (a full wizard + staging schema) versus a one-off script; accepted
  because the brief treats data integrity and non-silent overwrite as hard requirements, not
  a nice-to-have.
