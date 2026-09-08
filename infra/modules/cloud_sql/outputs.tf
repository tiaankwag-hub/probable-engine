output "connection_name" {
  value       = google_sql_database_instance.this.connection_name
  description = "Pass to Cloud Run's cloudsql_instances / --add-cloudsql-instances."
}

output "database_name" {
  value = google_sql_database.this.name
}

output "db_user" {
  value = google_sql_user.app.name
}

output "db_password_secret_id" {
  value       = google_secret_manager_secret.db_password.secret_id
  description = "Secret Manager secret holding the generated DB password alone — reference database_url_secret_id instead for Cloud Run's DATABASE_URL env var."
}

output "database_url_secret_id" {
  value       = google_secret_manager_secret.database_url.secret_id
  description = "Secret Manager secret holding the fully-composed DATABASE_URL DSN — this is what cloud_run_service's secret_env_vars should point DATABASE_URL at."
}

output "private_dsn_hint" {
  value       = "postgresql+psycopg://${var.db_user}:<from-secret>@/${var.database_name}?host=/cloudsql/${google_sql_database_instance.this.connection_name}"
  description = "Shape of the DATABASE_URL to build in Cloud Run's env — the Unix-socket form the Cloud SQL connector expects, not a host:port URL."
}
