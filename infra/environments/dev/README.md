# infra/environments/dev

Terraform root module for the `dev` GCP environment, composed from `infra/modules`.
All environment-specific values (project ID, region, domain) are supplied via `.tfvars` /
variables at apply time — never hard-coded.

Status: not yet implemented. Planned for Milestone 11. This environment is not configured,
applied, or provisioned during Milestone 0.
