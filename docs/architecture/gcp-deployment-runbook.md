# GCP Deployment Runbook (Milestone 11)

Every command in this document runs from **your own trusted workstation**, authenticated as
yourself (`gcloud auth login`) — never from a Claude Code session, per
`docs/architecture/roadmap.md`'s "Explicitly deferred to Milestone 11" section. This is the
exact, ordered sequence; each phase names precisely what to replace.

Read this whole document once before running anything — several steps depend on values only
produced by an earlier step (the load balancer's IP isn't known until after the first apply,
for instance), and the ordering below exists specifically to avoid backtracking.

## Phase 0 — Decisions you need before starting

Have these ready; they become Terraform variables or manual console inputs later.

| Decision | Where it's used |
|---|---|
| GCP project ID (new or existing) | `terraform.tfvars: project_id` |
| Region (default `us-central1` is fine unless you have a reason to pick another) | `terraform.tfvars: region` |
| A domain you control DNS for (e.g. `risk.yourcompany.com`) | `terraform.tfvars: domain` |
| Who should be able to sign in at all — everyone in your Workspace domain, or a specific group | `terraform.tfvars: iap_members` |
| A support email for the OAuth consent screen (any address at your org works) | IAP OAuth consent screen (Phase 3) |

## Phase 1 — Project, billing, tooling

```bash
gcloud auth login
gcloud projects create REPLACE_ME-your-project-id   # skip if the project already exists
gcloud config set project REPLACE_ME-your-project-id
gcloud beta billing projects link REPLACE_ME-your-project-id \
  --billing-account=REPLACE_ME-your-billing-account-id
```

Install Terraform (>= 1.7) and Docker on this workstation if not already present.

## Phase 2 — Terraform state bucket

Terraform can't create the bucket that holds its own state, so this one resource is created by
hand, once:

```bash
gsutil mb -p REPLACE_ME-your-project-id -l REPLACE_ME-your-region gs://REPLACE_ME-your-project-id-tfstate
gsutil versioning set on gs://REPLACE_ME-your-project-id-tfstate
```

Restrict who can read this bucket (`gsutil iam` or the console) — it will hold the
Terraform-generated Cloud SQL password after Phase 5.

Edit `infra/environments/production/backend.tf`, replacing `REPLACE_ME-tfstate` with the exact
bucket name you just created.

## Phase 3 — IAP OAuth consent screen (the one manual console step)

Terraform deliberately does not create this — a project's first OAuth consent screen requires
your organization's own support email and branding decisions, which is why it's a one-time
manual step rather than something automated (see `infra/environments/production/iap.tf`'s
comment for the reasoning).

1. Console → **APIs & Services → OAuth consent screen**. Choose **Internal** if every user is
   in your Google Workspace org, or **External** (and keep it in "Testing" status, adding
   specific test users) if not. Fill in the support email and app name.
2. Console → **APIs & Services → Credentials → Create Credentials → OAuth client ID**, type
   **Web application**. Name it anything (e.g. "Risk Platform IAP").
3. Copy the **Client ID** and **Client Secret** shown — you'll pass these to Terraform in
   Phase 5. Store the secret somewhere you can paste from (a password manager), not a file in
   this repo.

## Phase 4 — Bootstrap: enable APIs and create the container registry

This is a **targeted** apply — deliberately scoped to just the registry (plus the project APIs
it depends on) — because every Cloud Run service created later needs a real, already-pushed
image to reference, and that image needs somewhere to live first.

```bash
cd infra/environments/production
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars: fill in every REPLACE_ME (project_id, storage_bucket_name, domain,
# iap_oauth_client_id from Phase 3, iap_members). Leave iap_oauth_client_secret_value out of
# this file entirely — it's passed at apply time only, next.

terraform init
terraform fmt
terraform validate
terraform apply -target=module.artifact_registry \
  -var="iap_oauth_client_secret_value=REPLACE_ME-paste-the-client-secret-from-phase-3"
```

This enables every required GCP API and creates the Artifact Registry repository. Everything
else (Cloud SQL, the Cloud Run services, the load balancer) comes in Phase 6.

## Phase 5 — Build and push the four images

```bash
gcloud auth configure-docker REPLACE_ME-your-region-docker.pkg.dev

REPO="REPLACE_ME-your-region-docker.pkg.dev/REPLACE_ME-your-project-id/risk-platform"

docker build -f apps/api/Dockerfile    -t "$REPO/api:v1"    .
docker build -f apps/worker/Dockerfile -t "$REPO/worker:v1" .
docker build -f apps/mcp/Dockerfile    -t "$REPO/mcp:v1"    .
docker build -f apps/web/Dockerfile    -t "$REPO/web:v1"    apps/web

docker push "$REPO/api:v1"
docker push "$REPO/worker:v1"
docker push "$REPO/mcp:v1"
docker push "$REPO/web:v1"
```

In `terraform.tfvars`, set `image_tag = "v1"` (replacing the `initial` placeholder default) so
the full apply in Phase 6 creates every Cloud Run service pointing at a real image from the
start.

## Phase 6 — Full apply

```bash
terraform plan \
  -var="iap_oauth_client_secret_value=REPLACE_ME-paste-the-client-secret-from-phase-3"
# Read the plan. You should see: Cloud SQL, the storage bucket, the gemini-api-key secret
# container, four Cloud Run services, the load balancer + IAP backend services, two Cloud
# Scheduler jobs, and the remaining IAM bindings. Nothing here has touched a database yet.

terraform apply \
  -var="iap_oauth_client_secret_value=REPLACE_ME-paste-the-client-secret-from-phase-3"
```

Save the outputs — you need `load_balancer_ip` next, and `cloud_sql_connection_name`/
`api_service_url` are useful for troubleshooting.

## Phase 7 — Point DNS, wait for the certificate

```bash
terraform output load_balancer_ip
```

Create an `A` record for `REPLACE_ME-your-domain` pointing at that IP, with your DNS provider.
Then wait for Google's managed certificate to finish validating:

```bash
gcloud compute ssl-certificates describe risk-platform-cert --global --format='value(managed.status)'
# ACTIVE once DNS has propagated and Google has issued the cert — can take up to ~60 minutes.
```

Nothing at `https://REPLACE_ME-your-domain` will work correctly until this says `ACTIVE`.

## Phase 8 — Run migrations and seed the database

There is no bare-metal workstation access to Cloud SQL (it has no public IP, by design) —
run migrations the same way `docker-compose.yml`'s `migrate` service does locally, but as a
one-off Cloud Run Job reusing the `api` image:

```bash
gcloud run jobs create risk-platform-migrate \
  --project=REPLACE_ME-your-project-id \
  --region=REPLACE_ME-your-region \
  --image="$REPO/api:v1" \
  --set-cloudsql-instances="$(terraform output -raw cloud_sql_connection_name)" \
  --set-secrets="DATABASE_URL=REPLACE_ME-your-cloud-sql-instance-name-database-url:latest" \
  --command="sh" \
  --args="-c,cd apps/api && alembic upgrade head && cd /srv && python database/seed/seed.py" \
  --execute-now \
  --wait
```

(`REPLACE_ME-your-cloud-sql-instance-name` is `cloud_sql_instance_name` from your
`terraform.tfvars`, default `risk-platform-db` — the secret ID is
`<that>-database-url`, exactly as `infra/modules/cloud_sql/main.tf` names it.)

Confirm it succeeded: `gcloud run jobs executions list --job=risk-platform-migrate`.

Seeding here creates the same demo/fixture data local development uses — replace or extend
`database/seed/seed.py`'s real-user rows with your organization's actual risk owners before
relying on this for anything but a first smoke test (see Phase 10).

## Phase 9 — Populate the real secrets

Terraform already generated and stored the database password/DSN itself (Phase 6). The one
secret it couldn't fill in — because Terraform must never see real external credentials — is
your Gemini API key:

```bash
echo -n "REPLACE_ME-your-real-Gemini-API-key" | \
  gcloud secrets versions add gemini-api-key --data-file=-
```

Cloud Run services already reference `gemini-api-key` (Terraform wired that in Phase 6) — they
pick up the new version on their next revision or restart. If you'd rather not wait, redeploy:
`gcloud run services update risk-platform-api --region=REPLACE_ME-your-region` (a no-op deploy
that forces a fresh revision).

## Phase 10 — Provision real users

IAP (Phase 3's `iap_members`) controls **who can sign in at all**. It does not create rows in
this application's own `users`/`user_roles` tables — those still drive RBAC (ADR 0010), and a
person who can sign in but has no matching `users` row gets a clean 401 from `apps/api`
(`_load_current_user` in `apps/api/app/deps.py`), not a silent default role.

There is no admin UI for this yet (genuinely not built in any milestone — a good candidate for
follow-up work). For now, insert real users the same way `database/seed/seed.py` does, via a
one-off script run the same way as Phase 8's migration job, or by connecting through the
Cloud SQL Auth Proxy from your workstation:

```bash
cloud-sql-proxy REPLACE_ME-your-project-id:REPLACE_ME-your-region:REPLACE_ME-your-cloud-sql-instance-name &
psql "postgresql://risk_platform_app:$(gcloud secrets versions access latest --secret=REPLACE_ME-your-cloud-sql-instance-name-db-password)@localhost:5432/risk_platform"
```

Then insert into `users` and `user_roles` matching each real person's email (the same email
IAP will assert) and the role(s) they should hold — see `packages/shared/models/identity.py`
and `database/seed/seed.py`'s `seed_users` function for the exact shape.

## Phase 11 — Verify

- Visit `https://REPLACE_ME-your-domain` — you should hit Google's sign-in, then land on the
  dashboard with real (seeded, or your own) data.
- `curl -I https://REPLACE_ME-your-domain/api/healthz` — should return through the load
  balancer/IAP the same way the web app does, proving the `/api/*` path routing works.
- Cloud Scheduler: `gcloud scheduler jobs run capture-snapshot --location=REPLACE_ME-your-region`
  and confirm a new row appears via the Snapshots page.
- `gcloud run services list` — `risk-platform-worker` should show `min instances: 1`, confirming
  it's the always-on poller, not scaled to zero.

### Reaching the MCP gateway

`risk-platform-mcp` is internal-only by design (no `invoker_members` granted beyond what the
runbook adds for a specific human, deliberately — see `infra/environments/production/main.tf`).
To use it from a machine outside GCP (Claude Desktop, a local Claude Code session):

```bash
gcloud run services add-iam-policy-binding risk-platform-mcp \
  --region=REPLACE_ME-your-region \
  --member="user:REPLACE_ME-your-email@yourcompany.com" \
  --role="roles/run.invoker"

gcloud run services proxy risk-platform-mcp --region=REPLACE_ME-your-region --port=8080
```

That proxy tunnels `localhost:8080` to the real service using your own `gcloud` identity —
point your MCP client at `http://localhost:8080/mcp` with
`Authorization: Bearer $(gcloud auth print-identity-token --audiences=$(terraform output -raw iap_audience))`
(the token is valid for about an hour; re-run that command to refresh it).

## Explicitly not covered by this runbook

- **CI/CD pipeline and container scanning gates** — build these in your own CI system against
  this repo; Artifact Registry's built-in vulnerability scanning is already active once its API
  is enabled (Phase 4), at no extra Terraform.
- **A user-management admin UI** — Phase 10's manual `psql` step is a real gap; a proper
  "invite/assign role" page is good follow-up work, not built in Milestone 11.
- **Cloud-Tasks-native worker autoscaling** — `apps/worker` runs as a fixed single always-on
  Cloud Run instance (Phase 6), matching local dev's polling model exactly. See
  `docs/architecture/milestone-11-plan.md`'s "Explicitly still deferred" section for what a
  future push-based worker would need.
- **Staging/dev GCP environments** — only `production` was built; see
  `infra/environments/staging/README.md` and `infra/environments/dev/README.md` for how to
  extend this to more environments using the same modules.
