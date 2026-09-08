variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "job_name" {
  type = string
}

variable "schedule" {
  type        = string
  description = "Standard cron expression, evaluated in the given time_zone."
}

variable "time_zone" {
  type    = string
  default = "Etc/UTC"
}

variable "target_url" {
  type        = string
  description = "Full HTTPS URL of the internal endpoint to call, e.g. \"<api_url>/internal/jobs/capture-snapshot\"."
}

variable "invoker_service_account_email" {
  type        = string
  description = "Dedicated service account this job authenticates as. Must hold run.invoker on the target Cloud Run service and nothing else — see infra/environments/production for where that binding is granted."
}
