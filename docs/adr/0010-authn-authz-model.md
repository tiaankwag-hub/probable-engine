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

## Status update — Milestone 11 (identity code complete, not yet deployed)

Built exactly as decided above, no revision needed. `Settings.auth_mode` selects the identity
mechanism (`apps/api/app/deps.py`); `mock` (default) is unchanged from Milestone 1; `iap`
verifies Google IAP's signed assertion via `apps/api/app/iap_auth.py` against Google's public
keys, extracting only the `email` claim and never trusting a client-supplied role. The
mock-login endpoint is not merely gated in `iap` mode — it is absent from the route table
entirely (`apps/api/app/main.py` only registers it when `auth_mode == "mock"`), so there is no
runtime flag that could accidentally leave the backdoor reachable in production.

One addition beyond the original decision: the `iap` identity check accepts a Google-signed
assertion from either the header IAP itself injects (`X-Goog-IAP-JWT-Assertion`) or a forwarded
`Authorization: Bearer <token>` — needed because the MCP gateway (ADR 0009) never goes through
IAP at all, and forwards whatever Google ID token its own caller presented instead. Both are
verified identically; which header carried it doesn't change what's checked.
