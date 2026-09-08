# Google IAP in front of the ONE public entry point: a single external
# HTTPS load balancer fronting both apps/web (default) and apps/api
# (path-matched "/api/*", preserving apps/web's existing
# NEXT_PUBLIC_API_BASE_URL-based browser client unchanged). Both Cloud Run
# services stay on INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER (main.tf) — that
# ingress value permits traffic through this load balancer AND same-
# project internal callers (mcp's direct calls to api, Cloud Scheduler),
# never the public internet hitting either service's raw *.run.app URL.
#
# The OAuth client (iap_oauth_client_id / iap_oauth_client_secret_value)
# is NOT created by Terraform — a first-time IAP OAuth consent screen in a
# GCP project requires a one-time manual console step tied to your
# organization's own support email and branding. See the deployment
# runbook's "IAP OAuth consent screen" step for exactly what to click,
# once, before this file's first apply. Both backend services below reuse
# that same OAuth client.

data "google_project" "this" {
  project_id = var.project_id
}

module "web_service" {
  source                = "../../modules/cloud_run_service"
  project_id            = var.project_id
  region                = var.region
  service_name          = "risk-platform-web"
  image                 = "${module.artifact_registry.repository_url}/web:${var.image_tag}"
  container_port        = 3000
  service_account_email = module.web_sa.email
  ingress               = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
  invoker_members       = ["allUsers"] # gated by IAP at the load balancer, not by Cloud Run IAM directly
  allow_unauthenticated = true
  env_vars = {
    NEXT_PUBLIC_API_BASE_URL = "https://${var.domain}/api"
  }
}

resource "google_compute_region_network_endpoint_group" "web" {
  project               = var.project_id
  region                = var.region
  name                  = "risk-platform-web-neg"
  network_endpoint_type = "SERVERLESS"
  cloud_run {
    service = module.web_service.name
  }
}

resource "google_compute_region_network_endpoint_group" "api" {
  project               = var.project_id
  region                = var.region
  name                  = "risk-platform-api-neg"
  network_endpoint_type = "SERVERLESS"
  cloud_run {
    service = module.api_service.name
  }
}

resource "google_compute_backend_service" "web" {
  project = var.project_id
  name    = "risk-platform-web-backend"

  backend {
    group = google_compute_region_network_endpoint_group.web.id
  }

  iap {
    enabled              = true
    oauth2_client_id     = var.iap_oauth_client_id
    oauth2_client_secret = var.iap_oauth_client_secret_value
  }
}

resource "google_compute_backend_service" "api" {
  project = var.project_id
  name    = "risk-platform-api-backend"

  backend {
    group = google_compute_region_network_endpoint_group.api.id
  }

  iap {
    enabled              = true
    oauth2_client_id     = var.iap_oauth_client_id
    oauth2_client_secret = var.iap_oauth_client_secret_value
  }
}

# Same humans/groups get access to both — IAP evaluates this per backend
# service, so it has to be granted twice, but it's the same allowlist.
resource "google_iap_web_backend_service_iam_member" "web_members" {
  for_each            = toset(var.iap_members)
  project             = var.project_id
  web_backend_service = google_compute_backend_service.web.name
  role                = "roles/iap.httpsResourceAccessor"
  member              = each.value
}

resource "google_iap_web_backend_service_iam_member" "api_members" {
  for_each            = toset(var.iap_members)
  project             = var.project_id
  web_backend_service = google_compute_backend_service.api.name
  role                = "roles/iap.httpsResourceAccessor"
  member              = each.value
}

resource "google_compute_managed_ssl_certificate" "web" {
  project = var.project_id
  name    = "risk-platform-cert"
  managed {
    domains = [var.domain]
  }
}

resource "google_compute_url_map" "web" {
  project         = var.project_id
  name            = "risk-platform-lb"
  default_service = google_compute_backend_service.web.id

  path_matcher {
    name            = "api-routing"
    default_service = google_compute_backend_service.web.id

    path_rule {
      paths   = ["/api", "/api/*"]
      service = google_compute_backend_service.api.id
    }
  }

  host_rule {
    hosts        = [var.domain]
    path_matcher = "api-routing"
  }
}

resource "google_compute_target_https_proxy" "web" {
  project          = var.project_id
  name             = "risk-platform-https-proxy"
  url_map          = google_compute_url_map.web.id
  ssl_certificates = [google_compute_managed_ssl_certificate.web.id]
}

resource "google_compute_global_address" "web" {
  project = var.project_id
  name    = "risk-platform-lb-ip"
}

resource "google_compute_global_forwarding_rule" "web_https" {
  project               = var.project_id
  name                  = "risk-platform-lb-https"
  ip_address            = google_compute_global_address.web.id
  port_range            = "443"
  target                = google_compute_target_https_proxy.web.id
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

locals {
  # api's own backend service ID — apps/api verifies every assertion
  # against this exact audience (deps.py). Cross-check against
  # `gcloud compute backend-services describe risk-platform-api-backend
  # --global --format='value(id)'` after the first apply if `terraform
  # plan` ever complains about this attribute name on a provider upgrade.
  iap_audience = "/projects/${data.google_project.this.number}/global/backendServices/${google_compute_backend_service.api.generated_id}"
}
