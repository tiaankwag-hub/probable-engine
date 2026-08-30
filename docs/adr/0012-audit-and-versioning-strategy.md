# ADR 0012: Immutable audit log + full-state history + optimistic concurrency

## Status
Accepted

## Context
The brief requires that every authoritative modification produce an immutable audit event
and that change history is never destroyed, while also needing safe concurrent edits (e.g.
two risk owners editing related fields) and the ability to reconstruct "what did this risk
look like on date X" for the "What Changed?" executive view and reporting.

## Decision
Three complementary mechanisms, used together rather than any one alone:
1. **`audit_events`** — an insert-only log of every authoritative write (actor, timestamp,
   entity, entity_id, action, old_value, new_value, reason, source). No update/delete
   operation exists for this table at the application layer.
2. **`risk_history`** (and equivalent history where needed) — a full field-state snapshot
   per version, enabling point-in-time reconstruction without replaying deltas.
3. **`version` column + optimistic concurrency** on `risks` (and other frequently-edited
   entities) — a `PATCH` must supply the version it read; a stale version is rejected with
   `409`, preventing silent lost updates.

## Consequences
- Slightly more write amplification per change (one row in the entity table, one in its
  history table, one in `audit_events`) — accepted given the brief's explicit "never destroy
  change history" and auditability requirements.
- Database-level protections (no `DELETE`/`UPDATE` grants on `audit_events` for the
  application role) should back up the application-layer guarantee — tracked for the
  Milestone 1 migration/permissions setup.
- Snapshots (`snapshots`/`snapshot_risks`) are a separate, coarser-grained mechanism for
  fast period-over-period comparison and do not replace `risk_history`.
