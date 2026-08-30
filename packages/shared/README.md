# packages/shared

Cross-cutting code shared by `apps/api`, `apps/worker`, and `apps/mcp`: SQLAlchemy models,
Pydantic schemas, the audit-event writer, the object-storage abstraction (local filesystem in
dev, Cloud Storage in production), the import-mapping layer (spreadsheet/CSV column mapping,
validation, transformation into domain fields — see
`docs/adr/0008-import-mapping-layer.md`), RBAC/permission primitives, and structured logging
/ correlation-ID plumbing.

Nothing here depends on FastAPI request objects or Next.js — it is framework-agnostic domain
and infrastructure code.

Status: Milestone 1-2 complete — SQLAlchemy models, Pydantic schemas, the audit-event writer,
the RBAC permission matrix, the local-filesystem object store, the full import-mapping layer
(parser, transforms, default mapping, validation), the executive-dashboard aggregation
service, and the structured-logging/correlation-ID module this file had already (incorrectly)
described as done since Milestone 0 — see `docs/architecture/milestone-2-plan.md`.
