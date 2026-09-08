# Remote state in a GCS bucket you create by hand BEFORE the first `terraform
# init` (Terraform can't create the bucket that holds its own state). See
# the deployment runbook, step "Terraform state bucket". Enable versioning
# on it and restrict access tightly — this bucket holds the generated
# Cloud SQL password (see infra/modules/cloud_sql) alongside everything
# else Terraform manages.
#
# REPLACE bucket + prefix, then run `terraform init` (bucket names can't be
# variables in a backend block — this is the one place a literal is
# unavoidable).
terraform {
  backend "gcs" {
    bucket = "REPLACE_ME-tfstate"
    prefix = "production"
  }
}
