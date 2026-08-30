# infra/environments/production

Terraform root module for the `production` GCP environment, composed from `infra/modules`.
Applied from the separate corporate Windows workstation via Git, never from this development
environment. All environment-specific values are supplied via variables at apply time.

Status: not yet implemented. Planned for Milestone 11. This environment is not configured,
applied, or provisioned during Milestone 0.
