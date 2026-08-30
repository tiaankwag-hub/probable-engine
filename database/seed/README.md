# database/seed

Deterministic seed data for local development and CI: reference data (roles, risk
categories, scoring configuration, appetite thresholds) and fixture risks/controls/actions
for exercising the UI and tests without importing a real spreadsheet.

Contains no real organizational data — synthetic/fixture data only.

Status: Milestone 1 complete — `seed.py` (roles, one user per role, starter categories, the
active scoring config) and `generate_fixture.py` (produces `fixtures/risk_register_fixture.xlsx`,
20 synthetic rows matching the brief's 36-column schema — no real organizational data).
