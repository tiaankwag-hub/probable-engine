# database/migrations

Alembic migration scripts for the PostgreSQL schema. One migration per reviewable change;
no destructive migrations against authoritative data without an explicit, reviewed backfill
plan. Migrations must apply cleanly against both local Postgres and Cloud SQL PostgreSQL.

Status: Milestone 1 complete — see `apps/api/alembic/versions/` (Alembic's script location
is `apps/api/alembic`; this directory documents the migration policy, not the scripts
themselves).
