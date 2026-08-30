# Security

This project handles **confidential enterprise risk data**. See
`docs/security/threat-model.md` for the full STRIDE analysis and trust-boundary diagram.

## Baseline commitments

- No secrets, API keys, or service-account credentials are ever committed to this
  repository. Local development uses a git-ignored `.env`; production uses Secret Manager.
- No public production API — access is via an authenticated web app (SSO/IAP) and a governed
  MCP gateway only.
- RBAC is enforced server-side on every API route; frontend hiding is never relied upon
  alone.
- Every authoritative data modification produces an immutable audit event
  (`audit_events`); audit history is never deleted or edited.
- AI-generated content is never authoritative: it is stored as a reviewable suggestion and
  only becomes part of the risk record through an explicit, audited human approval.
- All inputs are validated (Pydantic); all database access is parameterized (SQLAlchemy);
  no raw SQL string interpolation.
- Dependency and container images are scanned in CI before deployment (see Milestone 11
  hardening plan in `docs/architecture/roadmap.md`).

## Reporting a vulnerability

This is a pre-release internal project with no external users yet. Report suspected
vulnerabilities to the project owner directly rather than via a public issue.

## Scope of this development environment

This machine is development-only. It does not hold GCP credentials, does not provision
cloud infrastructure, and does not store production data. Production deployment is
performed from a separate, access-controlled workstation.
