output "repository_url" {
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${var.repository_id}"
  description = "Prefix to build/push image references against, e.g. \"<repository_url>/api:<tag>\"."
}
