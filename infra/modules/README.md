# infra/modules

Reusable Terraform modules (Cloud Run service, Cloud SQL instance, Cloud Storage bucket,
Secret Manager binding, Cloud Tasks queue, Cloud Scheduler job, IAM service account +
least-privilege role bindings, Artifact Registry, logging/monitoring). Environments compose
these modules; no environment-specific values (project IDs, domains) are hard-coded here.

Status: not yet implemented. Deliberately out of scope until Milestone 11
(GCP deployment hardening). No GCP resources are created or configured during Milestone 0.
