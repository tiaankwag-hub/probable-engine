variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "service_name" {
  type = string
}

variable "image" {
  type        = string
  description = "Full Artifact Registry image reference, e.g. \"<region>-docker.pkg.dev/<project>/<repo>/api:<tag>\"."
}

variable "container_port" {
  type = number
}

variable "service_account_email" {
  type = string
}

variable "ingress" {
  type        = string
  default     = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  description = "One of INGRESS_TRAFFIC_ALL, INGRESS_TRAFFIC_INTERNAL_ONLY, INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER. Default is the safe default (ADR: no public production API) — only apps/web should ever override this to ALL, and even then it belongs behind IAP/SSO, not open to the internet unauthenticated."
}

variable "allow_unauthenticated" {
  type        = bool
  default     = false
  description = "Grants roles/run.invoker to allUsers. Leave false for every service except where the runbook explicitly calls for it (and even then, prefer fronting with IAP instead of setting this)."
}

variable "invoker_members" {
  type        = list(string)
  default     = []
  description = "IAM members (e.g. \"serviceAccount:web@project.iam.gserviceaccount.com\") granted run.invoker when allow_unauthenticated is false. This is the actual access-control list for an internal-only service."
}

variable "env_vars" {
  type    = map(string)
  default = {}
}

variable "secret_env_vars" {
  type = map(object({
    secret_id = string
    version   = optional(string, "latest")
  }))
  default     = {}
  description = "Maps an env var name to a Secret Manager secret. The service account must already have secretAccessor on each secret_id — this module does not grant it, to keep that decision visible at the call site next to whatever created the secret."
}

variable "cloudsql_connection_name" {
  type        = string
  default     = null
  description = "Cloud SQL instance connection_name to attach, or null for services that never touch the database (web, mcp)."
}

variable "min_instance_count" {
  type    = number
  default = 0
}

variable "max_instance_count" {
  type    = number
  default = 3
}

variable "startup_cpu_boost" {
  type    = bool
  default = true
}

variable "health_check_path" {
  type        = string
  default     = null
  description = "HTTP path for the startup probe (e.g. \"/healthz\"). Leave null to use Cloud Run's default TCP probe — the safer choice for a service (like apps/mcp) with no anonymous-accessible path to check."
}
