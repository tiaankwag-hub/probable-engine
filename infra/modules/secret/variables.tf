variable "project_id" {
  type = string
}

variable "secret_id" {
  type        = string
  description = "Secret Manager secret name, e.g. \"db-password\" or \"gemini-api-key\"."
}

variable "accessor_service_account_emails" {
  type        = list(string)
  default     = []
  description = "Service accounts granted secretAccessor on this secret. Only the service(s) that actually need this value at runtime — never a broad grant."
}
