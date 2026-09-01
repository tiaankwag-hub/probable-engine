from __future__ import annotations

import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/risk_platform_test"
)

import pytest
from sqlalchemy import text

from database.seed.seed import seed_categories, seed_roles, seed_scoring_config, seed_users
from packages.shared.db import get_engine, get_session_factory

TABLES_IN_DELETE_ORDER = [
    "audit_events",
    "risk_intake_sessions",
    "emerging_candidate_signals",
    "emerging_risk_candidates",
    "emerging_signals",
    "ai_suggestions",
    "ai_runs",
    "report_runs",
    "simulation_results",
    "simulation_runs",
    "simulation_configs",
    "scenario_risks",
    "scenarios",
    "import_row_errors",
    "import_column_mappings",
    "import_jobs",
    "background_jobs",
    "control_tests",
    "risk_controls",
    "controls",
    "actions",
    "issues",
    "incidents",
    "snapshot_risks",
    "snapshots",
    "risk_impact_scores",
    "risk_assessments",
    "risk_history",
    "risks",
    "risk_appetite",
    "risk_categories",
    "scoring_config",
    "user_roles",
    "users",
    "roles",
]


@pytest.fixture(autouse=True)
def clean_database():
    engine = get_engine()
    with engine.begin() as conn:
        for table in TABLES_IN_DELETE_ORDER:
            conn.execute(text(f'DELETE FROM "{table}"'))
    yield


@pytest.fixture
def db_session():
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def seeded(db_session):
    roles = seed_roles(db_session)
    seed_users(db_session, roles)
    seed_categories(db_session)
    seed_scoring_config(db_session)
    db_session.commit()
    return roles
