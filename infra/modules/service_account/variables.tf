variable "project_id" {
  type        = string
  description = "GCP project ID the service account belongs to."
}

variable "account_id" {
  type        = string
  description = "Service account ID (the part before @project.iam.gserviceaccount.com). Lowercase, max 30 chars."
}

variable "display_name" {
  type        = string
  description = "Human-readable name shown in the console."
}

variable "project_roles" {
  type        = list(string)
  default     = []
  description = "Project-level IAM roles to grant this service account. Keep empty and prefer resource-level bindings (Cloud SQL client, Secret Manager accessor, Cloud Run invoker) wherever a role exists at that scope — this list is for the few roles GCP only offers at project level."
}
