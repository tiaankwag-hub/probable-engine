# infra/environments/dev

Terraform root module for the `dev` GCP environment, composed from `infra/modules`.
All environment-specific values (project ID, region, domain) are supplied via `.tfvars` /
variables at apply time — never hard-coded.

Status: not built in Milestone 11 — only `production` was (see its README and
`docs/architecture/milestone-11-plan.md`). "Local development" in this project has always meant
Docker Compose (docs/architecture/01-target-architecture.md), not a `dev` GCP project — stand
this up only if your organization specifically wants a shared cloud dev/QA environment, by
copying `../production`'s `.tf` files here with a separate project/domain and backend prefix.
