# Creates the secret container only — never its value. A secret value
# passed through a Terraform variable ends up in the state file and in
# plan/apply logs in plaintext, which defeats the point of Secret Manager.
# Populate the actual value out-of-band with:
#   gcloud secrets versions add <secret_id> --data-file=-
# (see the deployment runbook) — Terraform only ever manages who can read
# it, never what it contains.

resource "google_secret_manager_secret" "this" {
  project   = var.project_id
  secret_id = var.secret_id

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_iam_member" "accessors" {
  for_each  = toset(var.accessor_service_account_emails)
  project   = var.project_id
  secret_id = google_secret_manager_secret.this.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${each.value}"
}
