# infra/environments/staging

Terraform root module for the `staging` GCP environment, composed from `infra/modules`.
All environment-specific values are supplied via variables at apply time.

Status: not built in Milestone 11 — only `production` was (see its README and
`docs/architecture/milestone-11-plan.md`). To stand up staging, copy that environment's `.tf`
files here, point `terraform.tfvars` at a separate project/domain, and use a different
`backend.tf` prefix — the modules underneath are already shared and reusable as-is.
