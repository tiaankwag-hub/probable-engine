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

Status: Milestone 1 complete — the `background_jobs` poller and the `import_commit` job type
are implemented and tested. Monte Carlo and reporting job types land in their own milestones
(6 and 5 respectively).
