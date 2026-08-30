# Architecture Decision Records

| # | Title |
|---|---|
| [0001](0001-monorepo-structure.md) | Monorepo with apps/ and packages/ separation |
| [0002](0002-fastapi-backend.md) | FastAPI + Pydantic + SQLAlchemy + Alembic for the backend |
| [0003](0003-nextjs-frontend.md) | Next.js + TypeScript + Tailwind for the frontend |
| [0004](0004-postgresql-datastore.md) | PostgreSQL as the sole system of record |
| [0005](0005-async-job-execution-model.md) | Async job execution via a swappable queue abstraction |
| [0006](0006-ai-provider-abstraction-and-human-review.md) | Provider-neutral AI abstraction with mandatory human review |
| [0007](0007-deterministic-risk-scoring.md) | Deterministic, database-configured risk scoring |
| [0008](0008-import-mapping-layer.md) | Explicit import-mapping layer decoupled from the domain model |
| [0009](0009-mcp-gateway-governance.md) | MCP gateway as a governed, permissioned API client |
| [0010](0010-authn-authz-model.md) | SSO/IAP for authentication, server-side RBAC for authorization |
| [0011](0011-object-storage-abstraction.md) | Object storage abstraction for files, evidence, and reports |
| [0012](0012-audit-and-versioning-strategy.md) | Immutable audit log + full-state history + optimistic concurrency |

New ADRs follow the same template (Status / Context / Decision / Consequences), numbered
sequentially, and are never edited retroactively to change a past decision — a changed
decision gets a new ADR that supersedes the old one (old one's Status updated to
"Superseded by ADR NNNN").
