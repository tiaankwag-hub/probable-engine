# apps/api

FastAPI / Pydantic / SQLAlchemy / Alembic backend. The single authoritative entry point for
all reads and writes to platform data.

Responsibilities: `/api/v1` REST surface, request validation, RBAC enforcement, audit event
emission, dispatching long-running work (Monte Carlo, report generation, AI calls) to
`apps/worker` instead of executing it inline, and orchestrating `packages/*` domain logic.

Route handlers stay thin: validation and dependency wiring only. Business rules live in
`packages/risk_engine`, `packages/simulations`, `packages/reporting`, `packages/ai`, and
`packages/shared`.

Status: Milestone 1-2 complete — Risk Register CRUD, risk-categories read, the full Import
Wizard flow, mock-auth, server-enforced RBAC, the Executive Dashboard endpoint, scoring-config
administration, and structured request-correlated logging. See
`docs/architecture/milestone-1-plan.md` and `docs/architecture/milestone-2-plan.md`.
