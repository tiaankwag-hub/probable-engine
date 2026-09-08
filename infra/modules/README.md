# infra/modules

Reusable Terraform modules, composed by `infra/environments/*`. No environment-specific
values (project IDs, domains) are hard-coded here — every module takes them as variables.

Status: **built in Milestone 11** (see `docs/architecture/milestone-11-plan.md`).

| Module | Provisions |
|---|---|
| `service_account` | One IAM service account + optional project-level role grants. |
| `artifact_registry` | A single Docker repository for all four container images. |
| `secret` | A Secret Manager secret container + accessor IAM bindings — never a value (see the module's own comment on why). |
| `storage_bucket` | A private, versioned GCS bucket + writer IAM bindings. |
| `cloud_sql` | A private (no public IP) Postgres 16 instance, database, app user, and a Terraform-generated password stored straight into Secret Manager. |
| `cloud_run_service` | A generic Cloud Run v2 service: image, env/secret env, optional Cloud SQL attachment, ingress, and an explicit invoker allowlist (never `allUsers` unless a caller opts in). |
| `scheduler_job` | A Cloud Scheduler job calling an internal Cloud Run endpoint via an OIDC-authenticated service account. |

## Explicitly not built here

- **Cloud Tasks queue** — `apps/worker` is deployed as an always-on Cloud Run service that
  keeps polling Postgres exactly like local dev (a health-check server was added just so
  Cloud Run has something to probe), not migrated to a Cloud-Tasks-push model. See the
  Milestone 11 plan's "Explicitly still deferred" section for why, and what a future push-based
  worker would need.
- **VPC / Serverless VPC Access connector** — not needed. Cloud Run reaches Cloud SQL through
  the built-in Cloud SQL connector (IAM-authorized, over Google's backbone), and no other
  private networking is required by this architecture.
- **Logging/monitoring dashboards, alerting policies** — Cloud Run and Cloud SQL already emit
  to Cloud Logging/Monitoring by default with zero extra Terraform; custom dashboards and
  alert policies are a genuinely separate, later exercise, not a blocker to a working
  deployment.
- **IAP OAuth brand/client, custom domain, DNS** — these require values only the deploying
  organization has (a support email, a domain, an identity provider decision) and, for the
  IAP OAuth consent screen specifically, at least one manual console step Terraform can't
  fully replace on a first-time setup. The deployment runbook covers exactly what to click and
  what to run instead.
