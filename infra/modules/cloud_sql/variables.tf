variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "instance_name" {
  type = string
}

variable "database_name" {
  type    = string
  default = "risk_platform"
}

variable "db_user" {
  type    = string
  default = "risk_platform_app"
}

variable "tier" {
  type        = string
  default     = "db-custom-2-7680"
  description = "Machine tier. The default is a reasonable small-production size — right-size for actual load before relying on it."
}

variable "client_service_account_emails" {
  type        = list(string)
  default     = []
  description = "Service accounts granted cloudsql.client (apps/api and apps/worker — the only two that ever touch the database)."
}

variable "deletion_protection" {
  type    = bool
  default = true
}
