# tests

Cross-cutting and end-to-end tests that don't live next to the code they test:
Playwright end-to-end suites, cross-service API integration tests, and role/access
(RBAC) test suites that exercise `apps/api` as a black box.

Unit tests for a given package/app live alongside that code (e.g.
`packages/risk_engine/tests/`), not here.

Status: not yet implemented. First suites (RBAC + risk register API integration) land in
Milestone 1.
