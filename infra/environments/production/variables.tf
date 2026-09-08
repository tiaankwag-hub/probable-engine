variable "project_id" {
  type        = string
  description = "REPLACE: your GCP project ID (e.g. \"acme-risk-platform-prod\")."
}

variable "region" {
  type        = string
  default     = "us-central1"
  description = "REPLACE if your organization standardizes on a different region."
}

variable "artifact_repo_id" {
  type    = string
  default = "risk-platform"
}

variable "cloud_sql_instance_name" {
  type    = string
  default = "risk-platform-db"
}

variable "storage_bucket_name" {
  type        = string
  description = "REPLACE: must be globally unique across all of GCS. \"<project_id>-risk-platform-storage\" is a safe pattern."
}

variable "image_tag" {
  type        = string
  default     = "initial"
  description = "Placeholder tag for the very first `terraform apply`, before any image has been pushed — see the runbook's ordering. Every deploy after that goes through `gcloud run deploy --image ...:<real-tag>` directly, which this config is set up to not fight (see cloud_run_service's lifecycle.ignore_changes)."
}

variable "domain" {
  type        = string
  description = "REPLACE: the domain end users will use to reach the app, e.g. \"risk.yourcompany.com\". You must control DNS for this domain."
}

variable "iap_oauth_client_id" {
  type        = string
  description = "REPLACE: OAuth client ID from the IAP OAuth consent screen you create by hand once (runbook step \"IAP OAuth consent screen\") — Terraform intentionally does not create this; see that module's/file's comment for why."
}

variable "iap_oauth_client_secret_value" {
  type        = string
  sensitive   = true
  description = "REPLACE at apply time via -var or TF_VAR_iap_oauth_client_secret_value, never committed to a .tfvars file. The OAuth client secret paired with iap_oauth_client_id. Terraform stores it directly into Secret Manager (see secretmanager.tf) and never writes it to a plan file others can read."
}

variable "iap_members" {
  type        = list(string)
  description = "REPLACE: who may sign in at all, as IAM members — e.g. [\"domain:yourcompany.com\"] for everyone in your Workspace domain, or [\"group:risk-platform-users@yourcompany.com\"] for a specific group. This is IAP's own access gate, separate from and in addition to this app's own RBAC."
}
