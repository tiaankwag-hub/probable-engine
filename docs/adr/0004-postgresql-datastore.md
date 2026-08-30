# ADR 0004: PostgreSQL as the sole system of record

## Status
Accepted

## Context
The domain has many relational entities (risks, controls, actions, assessments, history,
snapshots) with strong referential integrity needs (many-to-many risk↔control, versioned
history, audit trail) and a clear path to a managed production equivalent (Cloud SQL).

## Decision
PostgreSQL for all structured data, both locally (Docker Compose) and in production (Cloud
SQL for PostgreSQL). JSONB columns are used sparingly for genuinely variable-shape data
(`risk_history.field_state`, `snapshot_risks.frozen_state`, AI raw responses) — never as a
substitute for modeling a relationship properly.

## Consequences
- A single migration history (Alembic) applies identically to local and production
  databases, reducing environment drift.
- No polyglot persistence in v1 (no separate document/analytics store) — if reporting-scale
  analytics later need a warehouse, that is a future ADR, not a Milestone 0–11 concern.
- Structured data stays in Postgres; large binary content (evidence files, generated
  reports) goes to the object storage abstraction instead, keeping the database lean.
