variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "bucket_name" {
  type        = string
  description = "Globally-unique GCS bucket name, e.g. \"<project_id>-risk-platform-storage\"."
}

variable "writer_service_account_emails" {
  type        = list(string)
  default     = []
  description = "Service accounts granted objectAdmin (apps/api and apps/worker both read and write reports/evidence)."
}
