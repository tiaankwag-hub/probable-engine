# Object storage backing packages/shared's storage abstraction in
# production (docs/adr/0011-object-storage-abstraction.md) — generated
# reports and import evidence. Never public: uniform bucket-level access
# plus IAM-only, no allUsers/allAuthenticatedUsers binding anywhere here.

resource "google_storage_bucket" "this" {
  project                     = var.project_id
  name                        = var.bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = false

  versioning {
    enabled = true
  }

  public_access_prevention = "enforced"
}

resource "google_storage_bucket_iam_member" "writers" {
  for_each = toset(var.writer_service_account_emails)
  bucket   = google_storage_bucket.this.name
  role     = "roles/storage.objectAdmin"
  member   = "serviceAccount:${each.value}"
}
