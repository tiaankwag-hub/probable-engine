# Cloud Scheduler -> OIDC token -> Cloud Run's own IAM check. The target
# route (apps/api/app/routers/internal_jobs.py) has no app-level auth of
# its own by design; this OIDC identity plus the invoker binding IS the
# entire access control for it. audience = target_url matches the Cloud
# Run service's own URL, which is what Cloud Run's IAM check expects.

resource "google_cloud_scheduler_job" "this" {
  project   = var.project_id
  region    = var.region
  name      = var.job_name
  schedule  = var.schedule
  time_zone = var.time_zone

  http_target {
    http_method = "POST"
    uri         = var.target_url

    oidc_token {
      service_account_email = var.invoker_service_account_email
      audience               = var.target_url
    }
  }

  retry_config {
    retry_count = 2
  }
}
