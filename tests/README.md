# tests

Cross-cutting and end-to-end tests that don't live next to the code they test:
Playwright end-to-end suites, cross-service API integration tests, and role/access
(RBAC) test suites that exercise `apps/api` as a black box.

Unit tests for a given package/app live alongside that code (e.g.
`packages/risk_engine/tests/`, `apps/api/tests/`), not here.

Status: `e2e/` (Milestone 1) holds the Playwright specs — its own `package.json` since it's
a Node project independent of `apps/web`. RBAC and Risk Register API integration tests
turned out to belong with the API they test (`apps/api/tests/`) rather than here, since they
need the same FastAPI test fixtures; this directory is reserved for suites that genuinely
span multiple services.
