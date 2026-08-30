"""Idempotent local/dev seed data: roles, a user per role (for RBAC testing
and the mock-auth login flow), starter risk categories, and the active
scoring configuration (ADR 0007). No real organizational data — synthetic
fixtures only.

Usage:
    PYTHONPATH=. DATABASE_URL=... python database/seed/seed.py
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from packages.risk_engine.scoring import default_scoring_config
from packages.shared.db import get_session_factory
from packages.shared.models.identity import Role, RoleName, User, UserRole
from packages.shared.models.risk import RiskCategory
from packages.shared.models.scoring import ScoringConfig

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


def run() -> None:
    session = get_session_factory()()
    try:
        roles = seed_roles(session)
        seed_users(session, roles)
        seed_categories(session)
        seed_scoring_config(session)
        session.commit()
        print("Seed complete.")
    finally:
        session.close()


if __name__ == "__main__":
    run()
