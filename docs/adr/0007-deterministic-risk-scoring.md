# ADR 0007: Deterministic, database-configured risk scoring

## Status
Accepted

## Context
Impact scales, band thresholds, control-reduction formulas, and appetite thresholds are
exactly the kind of "business rule" the brief explicitly warns against hard-coding, because
they legitimately change over time (new scale definitions, revised appetite) and must remain
auditable/reproducible for past periods.

## Decision
- `scoring_config` (impact scale definitions, weighting, band thresholds, control-reduction
  formula parameters) and `risk_appetite` (per category/business unit) are database tables,
  versioned, never overwritten in place.
- Every `risk_assessments` row stores the `scoring_config_version` used, so a score computed
  in the past remains explainable even after the configuration changes later.
- `packages/risk_engine` is pure functions: `(inputs, config) -> scores/bands/appetite flag`,
  with no I/O, fully unit-testable, and is the *only* code allowed to write computed score
  fields on `risks`.
- AI may explain a score (e.g. "why is this residual band High") but never sets it.

## Consequences
- Changing a threshold is a data change (with its own audit trail via a config-change audit
  event), not a deployment.
- Requires a small admin UI/API for scoring-config management (Milestone 3, alongside
  appetite), rather than relying on database edits.
- Unit tests for `packages/risk_engine` become the primary correctness gate for the entire
  platform's numeric outputs and are treated as release-blocking from Milestone 2 onward.
