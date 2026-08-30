# ADR 0010: SSO/IAP for authentication, server-side RBAC for authorization

## Status
Accepted

## Context
The brief requires enterprise authentication (Google Identity/IAP or approved corporate SSO
in production), API-level RBAC, least privilege, and explicitly states frontend hiding is
insufficient. Local development must not require real SSO/IAP infrastructure.

## Decision
- Production: identity established by Google IAM/IAP or an approved corporate SSO in front
  of `apps/web`; `apps/api` verifies the identity token/JWT on every request (not just at the
  edge) and resolves roles from `user_roles`, never trusting a client-supplied role claim.
- Local development: a mock-auth mode with seeded users carrying explicit role assignments,
  so RBAC logic is exercised identically to production without standing up IAP.
- Authorization is enforced via a FastAPI dependency applied per route
  (`require_role`/`require_permission`), covered by a dedicated role/access test suite in
  `tests/` that runs against every route, not a sample.

## Consequences
- The same RBAC code path runs in dev and prod; only the identity-issuing mechanism differs.
- Real SSO/IAP integration work is deferred to Milestone 11 without blocking RBAC
  implementation and testing in Milestone 1 onward.
- Requires discipline to add a role/access test for every new route as part of its own PR,
  not as a separate follow-up.
