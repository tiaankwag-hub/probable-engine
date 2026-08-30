# packages/risk_engine

Deterministic, auditable risk scoring: impact-dimension aggregation, inherent score/band,
control-effectiveness reduction, residual score/band, appetite evaluation
(within/approaching/outside/material breach), and the priority-ranking engine.

Scoring configuration (impact scales, weights, band thresholds, priority weights) is read
from the database (`risk_scoring_config` / `risk_appetite` tables), never hard-coded, and every
config version is retained so past scores remain reproducible against the config in effect at
the time.

This package has no HTTP, database session, or UI concerns — it is pure functions over typed
inputs so it can be unit tested exhaustively and reused by both `apps/api` and `apps/worker`.
AI never writes to this package's outputs; see `docs/adr/0007-deterministic-risk-scoring.md`.

Status: not yet implemented. Core scoring lands in Milestone 2; appetite evaluation in
Milestone 3; priority engine after Milestone 4 (needs history/overdue signals).
