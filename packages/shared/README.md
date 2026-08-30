# packages/shared

Cross-cutting code shared by `apps/api`, `apps/worker`, and `apps/mcp`: SQLAlchemy models,
Pydantic schemas, the audit-event writer, the object-storage abstraction (local filesystem in
dev, Cloud Storage in production), the import-mapping layer (spreadsheet/CSV column mapping,
validation, transformation into domain fields — see
`docs/adr/0008-import-mapping-layer.md`), RBAC/permission primitives, and structured logging
/ correlation-ID plumbing.

Nothing here depends on FastAPI request objects or Next.js — it is framework-agnostic domain
and infrastructure code.

Status: Milestone 1 complete — SQLAlchemy models, Pydantic schemas, the audit-event writer,
the RBAC permission matrix, the local-filesystem object store, and the full import-mapping
layer (parser, transforms, default mapping, validation).
