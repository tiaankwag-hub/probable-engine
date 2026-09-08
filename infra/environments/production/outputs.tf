output "load_balancer_ip" {
  value       = google_compute_global_address.web.address
  description = "Point your domain's DNS A record at this IP (see the deployment runbook's DNS step)."
}

output "artifact_registry_repository_url" {
  value = module.artifact_registry.repository_url
}

output "cloud_sql_connection_name" {
  value = module.cloud_sql.connection_name
}

output "iap_audience" {
  value       = local.iap_audience
  description = "Set as apps/api's IAP_AUDIENCE — already wired automatically into the api Cloud Run service's env; surfaced here only for cross-checking against `gcloud`."
}

output "web_service_url" {
  value       = module.web_service.url
  description = "Cloud Run's own URL for the web service — not the public entry point (that's the load balancer IP/domain); useful for troubleshooting."
}

output "api_service_url" {
  value       = module.api_service.url
  description = "Cloud Run's own URL for the api service — this is what mcp calls directly and what MCP_API_BASE_URL is set to."
}
