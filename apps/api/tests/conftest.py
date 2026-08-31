from __future__ import annotations

import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/risk_platform_test"
)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from apps.api.app.deps import get_object_store
from apps.api.app.main import app
from database.seed.seed import (
    seed_categories,
    seed_roles,
    seed_scoring_config,
    seed_users,
)
from packages.shared.db import Base, get_engine, get_session_factory
from packages.shared.storage import LocalFileSystemStore

TABLES_IN_DELETE_ORDER = [
    "audit_events",
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


@pytest.fixture
def client(tmp_path, seeded):
    store = LocalFileSystemStore(tmp_path / "storage")
    app.dependency_overrides[get_object_store] = lambda: store
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def login(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/mock-login", json={"email": email})
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
