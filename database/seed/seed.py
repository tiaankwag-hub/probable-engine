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
from packages.shared.models.action import Action, ActionPriority, ActionStatus
from packages.shared.models.control import (
    Control,
    ControlAutomation,
    ControlStatus,
    ControlType,
    RiskControl,
)
from packages.shared.models.identity import Role, RoleName, User, UserRole
from packages.shared.models.risk import Risk, RiskBand, RiskCategory
from packages.shared.models.scoring import ScoringConfig
from packages.shared.risk_service import create_risk

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "risk_register_fixture.xlsx"

# Fabricated for this prototype — matches the control_effectiveness_1_5
# values already baked into the fixture spreadsheet's narrative (e.g. the
# unpatched-servers risk cites weak scanning/patching controls at 2/5).
CONTROL_METADATA: dict[str, dict] = {
    "CTRL-PAY-01": dict(
        name="Secondary payment processor failover",
        control_type=ControlType.CORRECTIVE, automation=ControlAutomation.MANUAL,
        design_effectiveness=3, operating_effectiveness=3,
    ),
    "CTRL-SEC-04": dict(
        name="Automated vulnerability scanning",
        control_type=ControlType.DETECTIVE, automation=ControlAutomation.AUTOMATED,
        design_effectiveness=3, operating_effectiveness=2,
    ),
    "CTRL-SEC-07": dict(
        name="Patch management SLA enforcement",
        control_type=ControlType.PREVENTIVE, automation=ControlAutomation.AUTOMATED,
        design_effectiveness=3, operating_effectiveness=2,
    ),
    "CTRL-PPL-02": dict(
        name="Cross-training and knowledge documentation",
        control_type=ControlType.PREVENTIVE, automation=ControlAutomation.MANUAL,
        design_effectiveness=2, operating_effectiveness=2,
    ),
    "CTRL-LEG-01": dict(
        name="Regulatory horizon scanning",
        control_type=ControlType.DETECTIVE, automation=ControlAutomation.MANUAL,
        design_effectiveness=2, operating_effectiveness=1,
    ),
    "CTRL-FIN-03": dict(
        name="Cloud billing alerts and scaling caps",
        control_type=ControlType.PREVENTIVE, automation=ControlAutomation.AUTOMATED,
        design_effectiveness=4, operating_effectiveness=4,
    ),
}

BAND_TO_PRIORITY = {
    RiskBand.EXTREME: ActionPriority.CRITICAL,
    RiskBand.HIGH: ActionPriority.HIGH,
    RiskBand.MODERATE: ActionPriority.MEDIUM,
    RiskBand.LOW: ActionPriority.LOW,
}

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


def _get_or_create_control(session, control_code: str) -> Control:
    existing = session.scalars(select(Control).where(Control.control_code == control_code)).first()
    if existing is not None:
        return existing
    meta = CONTROL_METADATA.get(
        control_code,
        dict(name=f"Control {control_code}", control_type=ControlType.DETECTIVE,
             automation=ControlAutomation.MANUAL, design_effectiveness=3, operating_effectiveness=3),
    )
    control = Control(control_code=control_code, status=ControlStatus.ACTIVE, **meta)
    session.add(control)
    session.flush()
    return control


def _parse_completion_percent(raw: str | None) -> int:
    if not raw:
        return 0
    try:
        return max(0, min(100, int(str(raw).strip().rstrip("%"))))
    except ValueError:
        return 0


def _seed_actions_and_controls_for_risk(session, risk: Risk, mapped: dict) -> None:
    for control_code in mapped.get("control_ids_raw", []):
        control = _get_or_create_control(session, control_code)
        exists = session.scalars(
            select(RiskControl).where(
                RiskControl.risk_id == risk.id, RiskControl.control_id == control.id
            )
        ).first()
        if exists is None:
            session.add(RiskControl(risk_id=risk.id, control_id=control.id))

    treatment_summary = mapped.get("treatment_summary")
    if not treatment_summary:
        return

    # Idempotent per risk: a prior partial run (e.g. an older seed.py version
    # that stopped short of this step — see the Milestone 3 fix note below)
    # must not create a second action for the same risk on re-run.
    has_action = session.scalars(select(Action).where(Action.risk_id == risk.id)).first()
    if has_action is not None:
        return

    completion = _parse_completion_percent(mapped.get("action_completion_raw"))
    due_date = mapped.get("action_due_date_raw")
    action_status = (
        ActionStatus.COMPLETED if completion >= 100
        else ActionStatus.IN_PROGRESS if completion > 0
        else ActionStatus.OPEN
    )
    action_count = session.scalar(select(func.count()).select_from(Action)) or 0
    action = Action(
        action_code=f"ACT-{action_count + 1:04d}",
        risk_id=risk.id,
        title=treatment_summary,
        owner_id=risk.owner_id,
        due_date=due_date,
        priority=BAND_TO_PRIORITY.get(risk.residual_band, ActionPriority.MEDIUM),
        status=action_status,
        completion_percent=completion,
        completed_date=due_date if action_status == ActionStatus.COMPLETED else None,
    )
    session.add(action)
    session.flush()


def seed_demo_risks(session) -> int:
    """Populates the Risk Register from the synthetic fixture spreadsheet
    (database/seed/fixtures/risk_register_fixture.xlsx — no real
    organizational data) so the UI has something to demonstrate immediately
    after `docker compose up`, along with the controls and treatment actions
    the fixture's narrative already implies.

    Idempotent *per row*, not as an all-or-nothing block: each fixture row's
    risk is created only if a risk with that risk_code doesn't already
    exist, but controls/actions are (re-)checked for every row every run.
    This matters in practice — a database seeded by the Milestone 1/2
    version of this function already has the 20 demo risks; without this,
    Milestone 3's upgrade would see "risks exist" and skip the whole
    function, silently leaving the new controls/actions tables empty even
    after `docker compose up --build`. Never touches a risk once it's
    already been assessed differently than the fixture (e.g. via the UI) —
    it only backfills controls/actions, it does not re-run create_risk for
    an existing risk_code.
    """
    if not FIXTURE_PATH.exists():
        return 0

    raw_rows = parse_rows(FIXTURE_PATH)
    import_rows = build_import_rows(raw_rows, DEFAULT_RISK_REGISTER_MAPPING)

    created = 0
    for row in import_rows:
        risk_code = row.mapped.get("risk_code")
        risk = session.scalars(select(Risk).where(Risk.risk_code == risk_code)).first()
        if risk is None:
            category = get_or_create_category(session, row.mapped.get("category_name"))
            owner = find_owner(session, row.mapped.get("owner_email"))
            fields, assessment = row_to_inputs(
                row.mapped,
                category_id=category.id if category else None,
                owner_id=owner.id if owner else None,
            )
            risk = create_risk(
                session,
                fields=fields,
                assessment_input=assessment,
                actor_email="seed@system",
                actor_id=None,
                source="seed",
                risk_code=risk_code,
            )
            session.flush()
            created += 1
        _seed_actions_and_controls_for_risk(session, risk, row.mapped)
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
        print(
            f"Seed complete. {created} demo risk(s) newly created "
            "(controls/actions are backfilled for existing risks too, so 0 doesn't mean nothing happened)."
        )
    finally:
        session.close()


if __name__ == "__main__":
    run()
