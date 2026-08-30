# ADR 0005: Async job execution via a swappable queue abstraction

## Status
Accepted

## Context
Monte Carlo simulation, report generation, AI calls, and emerging-signal ingestion must
never run inline in an HTTP request (brief's explicit constraint), but production (Cloud
Tasks) and local development (no extra infrastructure desired) need different queue
backends. Introducing a new infrastructure dependency (e.g. Redis) purely for local
development was considered and rejected as unnecessary complexity for the scale involved.

## Decision
Define a `JobQueue` interface in `packages/shared` with two implementations:
- **Production**: Cloud Tasks-backed — `apps/api` enqueues a task naming the job type and a
  reference ID; Cloud Run (`apps/worker`) receives the push.
- **Local development**: a Postgres-backed job table (`SELECT ... FOR UPDATE SKIP LOCKED`
  polling), so `docker compose up` needs nothing beyond Postgres itself.

`apps/api` and `apps/worker` code depends only on the `JobQueue` interface; the backend is
selected by configuration/environment, never by an `if environment == "prod"` branch inside
business logic.

## Consequences
- Local development has no Redis/RabbitMQ dependency, keeping the Compose stack minimal.
- The polling-based local queue has higher latency than Cloud Tasks; acceptable since local
  development prioritizes correctness/debuggability over throughput.
- Job idempotency must be designed in from the start (a job may be picked up more than once
  under retry), tracked as a requirement for Milestone 1's job-table schema, not deferred.
