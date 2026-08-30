# apps/worker

Background worker for asynchronous, potentially long-running jobs: Monte Carlo simulations
(risk-level and portfolio), PowerPoint/PDF report generation, AI provider calls, emerging-risk
signal ingestion/classification, and snapshot computation.

Production: triggered via Cloud Tasks, running as its own Cloud Run service (or Cloud Run Job).
Local development: a polling consumer against a Postgres-backed job table (see
`docs/adr/0005-async-job-execution-model.md`) so no extra infrastructure is required to run
locally.

The worker never accepts direct user input — it only consumes job records created by the API
and writes results back through the same domain packages the API uses, so scoring and
validation logic is never duplicated.

Status: not yet implemented. First job type lands in Milestone 6 (risk-level Monte Carlo); the
job-table plumbing itself may land earlier if a Milestone needs it for reporting.
