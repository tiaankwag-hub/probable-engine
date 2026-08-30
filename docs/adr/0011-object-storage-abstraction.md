# ADR 0011: Object storage abstraction for files, evidence, and reports

## Status
Accepted

## Context
Source import files, control/test evidence, and generated PDF/PPTX reports are binary
content that should not live in PostgreSQL, and production targets Cloud Storage while local
development should not require it.

## Decision
`packages/shared` defines an `ObjectStore` interface (`put`, `get`, `signed_url`, `delete`)
with a local-filesystem implementation for development/tests and a Cloud Storage
implementation for production, selected by configuration. All references to stored files in
the database (`controls.evidence`, `report_runs.generated_file`, `import_jobs.file_ref`) are
opaque keys resolved through this interface, never raw filesystem paths or bucket URLs baked
into application logic.

## Consequences
- No code path needs to know whether it's running against local disk or Cloud Storage.
- Client-facing downloads use short-lived signed URLs in production, avoiding public bucket
  ACLs.
- Local filesystem storage must be a volume mounted into the Compose containers so files
  survive container restarts during development.
