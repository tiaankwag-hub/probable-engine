output "email" {
  value       = google_service_account.this.email
  description = "Full service account email, for use as a Cloud Run runtime identity or an IAM member reference."
}

output "name" {
  value = google_service_account.this.name
}
