"""Idempotent local/dev seed data: roles, a user per role (for RBAC testing
and the mock-auth login flow), starter risk categories, and the active
scoring configuration (ADR 0007). No real organizational data — synthetic
fixtures only.

Usage:
    PYTHONPATH=. DATABASE_URL=... python database/seed/seed.py
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select

from packages.risk_engine.scoring import default_scoring_config
from packages.shared.db import get_session_factory
from packages.shared.import_service import find_owner, get_or_create_category, row_to_inputs
from packages.shared.importing.mapping import DEFAULT_RISK_REGISTER_MAPPING, build_import_rows
from packages.shared.importing.parser import parse_rows
from packages.shared.models.identity import Role, RoleName, User, UserRole
from packages.shared.models.risk import Risk, RiskCategory
from packages.shared.models.scoring import ScoringConfig
from packages.shared.risk_service import create_risk

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "risk_register_fixture.xlsx"

SEED_USERS = [
    ("viewer@example.com", "Val Viewer", RoleName.VIEWER),
    ("risk.owner@example.com", "Olivia Owner", RoleName.RISK_OWNER),
    ("control.owner@example.com", "Carl Controller", RoleName.CONTROL_OWNER),
    ("risk.manager@example.com", "Maria Manager", RoleName.RISK_MANAGER),
    ("executive@example.com", "Evan Executive", RoleName.EXECUTIVE),
    ("admin@example.com", "Ada Admin", RoleName.ADMINISTRATOR),
    ("auditor@example.com", "Audrey Auditor", RoleName.AUDITOR),
]

SEED_CATEGORIES = [
    "Operational",
    "Financial",
    "Cyber & Information Security",
    "Legal & Regulatory",
    "Strategic",
    "People & Culture",
    "Third Party & Vendor",
]


def seed_roles(session) -> dict[RoleName, Role]:
    roles: dict[RoleName, Role] = {}
    for role_name in RoleName:
        existing = session.scalars(select(Role).where(Role.name == role_name)).first()
        if existing is None:
            existing = Role(name=role_name)
            session.add(existing)
            session.flush()
        roles[role_name] = existing
    return roles


def seed_users(session, roles: dict[RoleName, Role]) -> None:
    for email, display_name, role_name in SEED_USERS:
        user = session.scalars(select(User).where(User.email == email)).first()
        if user is None:
            user = User(email=email, display_name=display_name, status="active")
            session.add(user)
            session.flush()
        has_role = session.scalars(
            select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == roles[role_name].id)
        ).first()
        if has_role is None:
            session.add(UserRole(user_id=user.id, role_id=roles[role_name].id))


def seed_categories(session) -> None:
    for name in SEED_CATEGORIES:
        existing = session.scalars(select(RiskCategory).where(RiskCategory.name == name)).first()
        if existing is None:
            session.add(RiskCategory(name=name))


def seed_scoring_config(session) -> None:
    existing = session.scalars(
        select(ScoringConfig).where(ScoringConfig.is_active.is_(True))
    ).first()
    if existing is not None:
        return
    default = default_scoring_config()
    session.add(
        ScoringConfig(
            version=default.version,
            config={
                "dimension_weights": default.dimension_weights,
                "band_thresholds": [list(t) for t in default.band_thresholds],
                "max_reduction_fraction": default.max_reduction_fraction,
                "max_control_effectiveness": default.max_control_effectiveness,
            },
            is_active=True,
            created_at=datetime.now(timezone.utc),
            created_by=None,
        )
    )


def seed_demo_risks(session) -> int:
    """Populates the Risk Register from the synthetic fixture spreadsheet
    (database/seed/fixtures/risk_register_fixture.xlsx — no real
    organizational data) so the UI has something to demonstrate immediately
    after `docker compose up`. Idempotent: does nothing if any risk already
    exists, so it's safe to run this seed script on every container start.
    """
    existing_count = session.scalar(select(func.count()).select_from(Risk)) or 0
    if existing_count > 0:
        return 0
    if not FIXTURE_PATH.exists():
        return 0

    raw_rows = parse_rows(FIXTURE_PATH)
    import_rows = build_import_rows(raw_rows, DEFAULT_RISK_REGISTER_MAPPING)

    created = 0
    for row in import_rows:
        category = get_or_create_category(session, row.mapped.get("category_name"))
        owner = find_owner(session, row.mapped.get("owner_email"))
        fields, assessment = row_to_inputs(
            row.mapped,
            category_id=category.id if category else None,
            owner_id=owner.id if owner else None,
        )
        create_risk(
            session,
            fields=fields,
            assessment_input=assessment,
            actor_email="seed@system",
            actor_id=None,
            source="seed",
            risk_code=row.mapped.get("risk_code"),
        )
        created += 1
    return created


def run() -> None:
    session = get_session_factory()()
    try:
        roles = seed_roles(session)
        seed_users(session, roles)
        seed_categories(session)
        seed_scoring_config(session)
        session.commit()
        created = seed_demo_risks(session)
        session.commit()
        print(f"Seed complete. {created} demo risk(s) created (0 means already seeded).")
    finally:
        session.close()


if __name__ == "__main__":
    run()
