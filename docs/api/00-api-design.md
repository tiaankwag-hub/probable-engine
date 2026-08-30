# API Design

## Conventions

- All routes are versioned under `/api/v1`. Breaking changes ship as `/api/v2`; `v1` is
  supported until clients migrate.
- JSON in, JSON out. Pagination via `?page=&page_size=` with `X-Total-Count` in the response
  header; filtering via explicit query parameters per resource (no free-form query language
  in v1).
- Every response includes a correlation ID (`X-Request-Id`, generated if not supplied) echoed
  in logs and in `audit_events.source` metadata.
- Errors follow a consistent envelope: `{"error": {"code", "message", "details"}}` with
  standard HTTP status codes (400 validation, 401 unauthenticated, 403 unauthorized, 404,
  409 version conflict, 422 semantic validation, 429 rate limited, 500).
- Mutations that affect authoritative data require an `If-Match`-style version field in the
  body (`version`) and return `409` on mismatch (optimistic concurrency, see domain model).
- Long-running work returns `202 Accepted` with a resource representing the job/run
  (`{"id", "status", "poll_url"}`); clients poll `GET` on that resource. No webhook callback
  in v1.
- Route handlers only validate and orchestrate; scoring, appetite evaluation, and priority
  ranking are computed in `packages/risk_engine`, never inline in a handler.

## Resource groups

### Risks
```
GET    /api/v1/risks                    list, filter, paginate, sort
POST   /api/v1/risks                    create (Risk Owner+)
GET    /api/v1/risks/{id}               detail
PATCH  /api/v1/risks/{id}                update (optimistic concurrency)
GET    /api/v1/risks/{id}/controls      linked controls
GET    /api/v1/risks/{id}/actions       linked actions
GET    /api/v1/risks/{id}/history       version history (risk_history)
GET    /api/v1/risks/{id}/assessments   assessment history
POST   /api/v1/risks/{id}/assessments   record a new assessment (triggers rescoring)
```
No hard delete endpoint — risks are retired via `status`, preserving history and audit trail.

### Categories & appetite
```
GET    /api/v1/risk-categories
GET    /api/v1/risk-appetite
PATCH  /api/v1/risk-appetite/{id}        (Administrator/Risk Manager)
GET    /api/v1/scoring-config            current + version history
PATCH  /api/v1/scoring-config            creates a new version (Administrator)
```

### Controls & assurance
```
GET    /api/v1/controls
POST   /api/v1/controls
GET    /api/v1/controls/{id}
PATCH  /api/v1/controls/{id}
GET    /api/v1/controls/{id}/tests
POST   /api/v1/controls/{id}/tests
```

### Actions, issues, incidents
```
GET    /api/v1/actions                  supports ?overdue=true
POST   /api/v1/actions
PATCH  /api/v1/actions/{id}
GET    /api/v1/issues
POST   /api/v1/issues
GET    /api/v1/incidents
POST   /api/v1/incidents
```

### Import
```
POST   /api/v1/imports                       upload file, returns job (status=uploaded)
GET    /api/v1/imports/{id}/columns          inspected source columns
PUT    /api/v1/imports/{id}/mapping          set source->domain mapping
POST   /api/v1/imports/{id}/validate         run validation, returns issues
GET    /api/v1/imports/{id}/preview          preview mapped/transformed rows
POST   /api/v1/imports/{id}/commit           commit (202, async for large files); emits audit event
```

### Dashboard
```
GET    /api/v1/dashboard/executive
GET    /api/v1/dashboard/governance
GET    /api/v1/dashboard/what-changed?since_snapshot=
```

### Snapshots
```
GET    /api/v1/snapshots
POST   /api/v1/snapshots                 (Administrator/Risk Manager; usually scheduler-triggered)
GET    /api/v1/snapshots/{id}
```

### Scenarios
```
GET    /api/v1/scenarios
POST   /api/v1/scenarios
GET    /api/v1/scenarios/{id}
PATCH  /api/v1/scenarios/{id}
GET    /api/v1/scenarios/{id}/exposure   combined scenario exposure (may trigger simulation)
```

### Simulations
```
POST   /api/v1/simulations               create config + enqueue run, 202
GET    /api/v1/simulations/{id}          run status + results when complete
GET    /api/v1/simulations?risk_id=      history for a risk
POST   /api/v1/simulations/portfolio     portfolio run, 202
```

### Emerging risks
```
GET    /api/v1/emerging-risks                       candidates, filterable by lifecycle_status
GET    /api/v1/emerging-risks/{id}
PATCH  /api/v1/emerging-risks/{id}                   lifecycle transition (human-only)
POST   /api/v1/emerging-risks/{id}/link-existing-risk
```

### AI
```
POST   /api/v1/ai/executive-summary      202, enqueues ai_runs
POST   /api/v1/ai/risk-analysis          {risk_id}, 202
GET    /api/v1/ai/runs/{id}
GET    /api/v1/ai/suggestions?status=pending
POST   /api/v1/ai/suggestions/{id}/approve    applies change via normal risk-update path
POST   /api/v1/ai/suggestions/{id}/reject
```

### Reports
```
POST   /api/v1/reports/powerpoint        {template, period, scope}, 202
POST   /api/v1/reports/pdf               {period, scope}, 202
GET    /api/v1/reports/runs/{id}         status + download reference when complete
```

### Admin
```
GET/POST/PATCH  /api/v1/admin/users
GET/POST/PATCH  /api/v1/admin/roles
GET             /api/v1/admin/audit-events   filterable, read-only
```

### Health & meta
```
GET /healthz     liveness
GET /readyz      readiness (DB reachable, migrations current)
```

## RBAC matrix (summary)

| Resource / action | Viewer | Risk Owner | Control Owner | Risk Manager | Executive | Administrator | Auditor |
|---|---|---|---|---|---|---|---|
| View risks/dashboards | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Create/edit own risks | ❌ | ✅ (owned) | ❌ | ✅ | ❌ | ✅ | ❌ |
| Edit any risk | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ |
| Manage controls (own) | ❌ | ❌ | ✅ (owned) | ✅ | ❌ | ✅ | ❌ |
| Record control tests | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ | ❌ |
| Manage actions | ❌ | ✅ (owned) | ✅ (owned) | ✅ | ❌ | ✅ | ❌ |
| Configure appetite/scoring config | ❌ | ❌ | ❌ | ✅ (propose) | ❌ | ✅ (approve/apply) | ❌ |
| Run imports | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ |
| Run simulations/scenarios | ❌ | ✅ (own risks) | ❌ | ✅ | ✅ (view results) | ✅ | ❌ |
| Approve AI suggestions | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ |
| Review emerging-risk candidates | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ |
| Generate reports | ❌ | ❌ | ❌ | ✅ | ✅ (request) | ✅ | ✅ (view runs) |
| Manage users/roles | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| Read audit log | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |

Enforced server-side via a FastAPI dependency (`require_role(...)` / `require_permission(...)`)
on every route — never relied upon in the frontend alone. Exact permission scoping
(department-scoped ownership checks etc.) is implemented as part of Milestone 1 and covered
by the role/access test suite in `tests/`.
