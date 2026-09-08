# One service account per deployable service (api, worker, mcp, scheduler,
# github-deployer), never one shared identity — so a compromise or a
# mistake in one service's permissions can't reach another's. See
# docs/security/threat-model.md's least-privilege principle.

resource "google_service_account" "this" {
  project      = var.project_id
  account_id   = var.account_id
  display_name = var.display_name
}

resource "google_project_iam_member" "project_roles" {
  for_each = toset(var.project_roles)
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.this.email}"
}
