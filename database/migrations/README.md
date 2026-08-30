# database/migrations

Alembic migration scripts for the PostgreSQL schema. One migration per reviewable change;
no destructive migrations against authoritative data without an explicit, reviewed backfill
plan. Migrations must apply cleanly against both local Postgres and Cloud SQL PostgreSQL.

Status: not yet implemented. First migration (core Milestone 1 tables) lands in Milestone 1.
