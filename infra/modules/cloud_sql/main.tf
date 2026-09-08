# Postgres 16, matching docs/adr/0004-postgresql-datastore.md. No public
# IP at all (ipv4_enabled = false) — Cloud Run reaches it exclusively via
# the built-in Cloud SQL connector (an encrypted tunnel authorized by
# `roles/cloudsql.client` on the calling service account, not by network
# routing), so no VPC or Serverless VPC Access connector is needed for
# this to be private. See docs/security/threat-model.md.

resource "google_sql_database_instance" "this" {
  project             = var.project_id
  name                = var.instance_name
  region              = var.region
  database_version    = "POSTGRES_16"
  deletion_protection = var.deletion_protection

  settings {
    tier = var.tier

    ip_configuration {
      ipv4_enabled = false
    }

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
    }
  }
}

resource "google_sql_database" "this" {
  project  = var.project_id
  instance = google_sql_database_instance.this.name
  name     = var.database_name
}

# The password is generated once by Terraform and never re-read from
# state on subsequent applies (lifecycle.ignore_changes) — rotate it by
# tainting this resource deliberately, not by editing tfvars.
resource "random_password" "db_password" {
  length  = 32
  special = false # simplest safe superset for a DSN connection string
}

resource "google_sql_user" "app" {
  project  = var.project_id
  instance = google_sql_database_instance.this.name
  name     = var.db_user
  password = random_password.db_password.result
}

resource "google_secret_manager_secret" "db_password" {
  project   = var.project_id
  secret_id = "${var.instance_name}-db-password"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "db_password" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = random_password.db_password.result
}

resource "google_secret_manager_secret_iam_member" "db_password_accessors" {
  for_each  = toset(var.client_service_account_emails)
  project   = var.project_id
  secret_id = google_secret_manager_secret.db_password.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${each.value}"
}

# apps/api and apps/worker read one DATABASE_URL, not separate host/user/
# password fields (packages/shared config), so this module composes the
# full DSN itself — the only place the password and connection details
# ever meet — and hands out the finished string as its own secret. The
# Unix-socket form is what the Cloud SQL connector expects when a Cloud
# Run service has this instance attached as a volume (cloud_run_service
# module's cloudsql_connection_name).
resource "google_secret_manager_secret" "database_url" {
  project   = var.project_id
  secret_id = "${var.instance_name}-database-url"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "database_url" {
  secret = google_secret_manager_secret.database_url.id
  secret_data = "postgresql+psycopg://${var.db_user}:${random_password.db_password.result}@/${var.database_name}?host=/cloudsql/${google_sql_database_instance.this.connection_name}"
}

resource "google_secret_manager_secret_iam_member" "database_url_accessors" {
  for_each  = toset(var.client_service_account_emails)
  project   = var.project_id
  secret_id = google_secret_manager_secret.database_url.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${each.value}"
}

resource "google_project_iam_member" "sql_clients" {
  for_each = toset(var.client_service_account_emails)
  project  = var.project_id
  role     = "roles/cloudsql.client"
  member   = "serviceAccount:${each.value}"
}
