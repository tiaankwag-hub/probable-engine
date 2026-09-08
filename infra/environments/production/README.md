# infra/environments/production

Terraform root module for the `production` GCP environment, composed from `infra/modules`.
**Applied from your own trusted workstation, never from a Claude Code session** — see
`docs/architecture/roadmap.md`'s "Explicitly deferred to Milestone 11" section and the
deployment runbook (`docs/architecture/gcp-deployment-runbook.md`) for exactly why and how.

Status: **built in Milestone 11** (`docs/architecture/milestone-11-plan.md`). Not yet applied —
no GCP resources exist from this configuration until you run `terraform apply` yourself.

What this provisions: Artifact Registry, Cloud SQL (private, no public IP), a Storage bucket,
Secret Manager secrets, five least-privilege service accounts, four Cloud Run v2 services
(web, api, worker, mcp), an external HTTPS load balancer with Google IAP in front of web and
api, and two Cloud Scheduler jobs. See `infra/modules/README.md` for what's deliberately not
built (Cloud Tasks queue, VPC, monitoring dashboards) and why.

Read `docs/architecture/gcp-deployment-runbook.md` before running anything here — it covers
the manual prerequisites (state bucket, IAP OAuth consent screen) that must exist before
`terraform init`/`apply` will work at all, in the order they need to happen.
