locals {
  services = [
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudscheduler.googleapis.com",
    "iap.googleapis.com",
    "compute.googleapis.com",
    "cloudresourcemanager.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each           = toset(local.services)
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

module "artifact_registry" {
  source        = "../../modules/artifact_registry"
  project_id    = var.project_id
  region        = var.region
  repository_id = var.artifact_repo_id

  depends_on = [google_project_service.apis]
}

# One identity per service (least privilege, never shared) — ADR:
# docs/security/threat-model.md.
module "api_sa" {
  source       = "../../modules/service_account"
  project_id   = var.project_id
  account_id   = "risk-platform-api"
  display_name = "Risk Platform - apps/api"

  depends_on = [google_project_service.apis]
}

module "worker_sa" {
  source       = "../../modules/service_account"
  project_id   = var.project_id
  account_id   = "risk-platform-worker"
  display_name = "Risk Platform - apps/worker"

  depends_on = [google_project_service.apis]
}

module "mcp_sa" {
  source       = "../../modules/service_account"
  project_id   = var.project_id
  account_id   = "risk-platform-mcp"
  display_name = "Risk Platform - apps/mcp"

  depends_on = [google_project_service.apis]
}

module "web_sa" {
  source       = "../../modules/service_account"
  project_id   = var.project_id
  account_id   = "risk-platform-web"
  display_name = "Risk Platform - apps/web"

  depends_on = [google_project_service.apis]
}

module "scheduler_sa" {
  source       = "../../modules/service_account"
  project_id   = var.project_id
  account_id   = "risk-platform-scheduler"
  display_name = "Risk Platform - Cloud Scheduler invoker"

  depends_on = [google_project_service.apis]
}

module "cloud_sql" {
  source          = "../../modules/cloud_sql"
  project_id      = var.project_id
  region          = var.region
  instance_name   = var.cloud_sql_instance_name
  client_service_account_emails = [
    module.api_sa.email,
    module.worker_sa.email,
  ]

  depends_on = [google_project_service.apis]
}

module "storage_bucket" {
  source      = "../../modules/storage_bucket"
  project_id  = var.project_id
  region      = var.region
  bucket_name = var.storage_bucket_name
  writer_service_account_emails = [
    module.api_sa.email,
    module.worker_sa.email,
  ]

  depends_on = [google_project_service.apis]
}

module "gemini_api_key" {
  source     = "../../modules/secret"
  project_id = var.project_id
  secret_id  = "gemini-api-key"
  accessor_service_account_emails = [
    module.api_sa.email,
    module.worker_sa.email,
  ]

  depends_on = [google_project_service.apis]
}

# --- Cloud Run services -----------------------------------------------

module "api_service" {
  source                 = "../../modules/cloud_run_service"
  project_id             = var.project_id
  region                 = var.region
  service_name           = "risk-platform-api"
  image                  = "${module.artifact_registry.repository_url}/api:${var.image_tag}"
  container_port         = 8000
  service_account_email  = module.api_sa.email
  # INTERNAL_LOAD_BALANCER, not INTERNAL_ONLY: this ingress value is a
  # superset — it still allows same-project internal callers (mcp's
  # direct Cloud-Run-to-Cloud-Run calls, Cloud Scheduler) AND traffic
  # routed through the load balancer below (iap.tf), which is how the
  # browser reaches "/api/*" without any change to apps/web's existing
  # NEXT_PUBLIC_API_BASE_URL-based client code.
  ingress                  = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
  health_check_path        = "/healthz"
  cloudsql_connection_name = module.cloud_sql.connection_name
  invoker_members = [
    "serviceAccount:${module.mcp_sa.email}",
    "serviceAccount:${module.scheduler_sa.email}",
  ]
  env_vars = {
    AUTH_MODE          = "iap"
    IAP_AUDIENCE       = local.iap_audience
    STORAGE_ROOT       = "gs://${module.storage_bucket.bucket_name}"
    CORS_ALLOW_ORIGINS = jsonencode(["https://${var.domain}"])
  }
  secret_env_vars = {
    DATABASE_URL = {
      secret_id = module.cloud_sql.database_url_secret_id
    }
    GEMINI_API_KEY = {
      secret_id = module.gemini_api_key.secret_id
    }
  }
}

module "worker_service" {
  source                 = "../../modules/cloud_run_service"
  project_id             = var.project_id
  region                 = var.region
  service_name           = "risk-platform-worker"
  image                  = "${module.artifact_registry.repository_url}/worker:${var.image_tag}"
  container_port         = 8080
  service_account_email  = module.worker_sa.email
  ingress                = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  health_check_path      = "/"
  cloudsql_connection_name = module.cloud_sql.connection_name
  min_instance_count     = 1
  max_instance_count     = 1 # always-on poller, not autoscaled — see milestone-11-plan.md
  invoker_members        = []
  env_vars = {
    STORAGE_ROOT = "gs://${module.storage_bucket.bucket_name}"
  }
  secret_env_vars = {
    DATABASE_URL = {
      secret_id = module.cloud_sql.database_url_secret_id
    }
    GEMINI_API_KEY = {
      secret_id = module.gemini_api_key.secret_id
    }
  }
}

module "mcp_service" {
  source                = "../../modules/cloud_run_service"
  project_id            = var.project_id
  region                = var.region
  service_name          = "risk-platform-mcp"
  image                 = "${module.artifact_registry.repository_url}/mcp:${var.image_tag}"
  container_port        = 8080
  service_account_email = module.mcp_sa.email
  ingress               = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  invoker_members       = [] # see the runbook's "Reaching the MCP gateway" section
  env_vars = {
    MCP_API_BASE_URL      = module.api_service.url
    MCP_IDENTITY_ISSUER_URL = "https://accounts.google.com"
  }
}

# --- Scheduled jobs ------------------------------------------------------
# The invoker grant scheduler_sa needs is on api's own invoker_members
# above (least privilege: exactly this one Cloud Run service, not a
# project-wide roles/run.invoker).

module "ingest_emerging_signals_job" {
  source                         = "../../modules/scheduler_job"
  project_id                     = var.project_id
  region                         = var.region
  job_name                       = "ingest-emerging-signals"
  schedule                       = "0 6 * * *" # daily 06:00 UTC — adjust to your risk team's cadence
  target_url                     = "${module.api_service.url}/internal/jobs/ingest-emerging-signals"
  invoker_service_account_email  = module.scheduler_sa.email
}

module "capture_snapshot_job" {
  source                         = "../../modules/scheduler_job"
  project_id                     = var.project_id
  region                         = var.region
  job_name                       = "capture-snapshot"
  schedule                       = "0 1 1 * *" # monthly on the 1st, 01:00 UTC — adjust to your reporting cadence
  target_url                     = "${module.api_service.url}/internal/jobs/capture-snapshot"
  invoker_service_account_email  = module.scheduler_sa.email
}
