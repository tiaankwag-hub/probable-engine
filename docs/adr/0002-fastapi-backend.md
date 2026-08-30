# ADR 0002: FastAPI + Pydantic + SQLAlchemy + Alembic for the backend

## Status
Accepted

## Context
The brief specifies this stack directly. It needs to support strict input validation
(scoring inputs, import mapping), async I/O for a worker/queue model, typed OpenAPI-driven
client generation for `apps/web`, and mature migration tooling for a schema that will grow
across 11 milestones.

## Decision
- FastAPI for routing and dependency-injected RBAC/auth checks.
- Pydantic v2 models for all request/response schemas (separate from SQLAlchemy ORM models).
- SQLAlchemy (2.x style) for the ORM layer, used identically by `apps/api` and `apps/worker`
  via `packages/shared`.
- Alembic for migrations, one migration per reviewable schema change.

## Consequences
- OpenAPI schema is generated automatically and used to produce the TypeScript client for
  `apps/web`, keeping frontend/backend contracts in sync without hand-written types.
- Pydantic schemas are kept distinct from ORM models so API contracts can evolve
  independently of storage schema where needed.
- Route handlers must stay thin (validation + orchestration only) per the project's own
  quality bar — enforced by code review, not tooling, tracked as a standing constraint.
