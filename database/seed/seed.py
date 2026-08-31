"""Idempotent local/dev seed data: roles, a user per role (for RBAC testing
and the mock-auth login flow), starter risk categories, and the active
scoring configuration (ADR 0007). No real organizational data — synthetic
fixtures only.

Usage:
    PYTHONPATH=. DATABASE_URL=... python database/seed/seed.py
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func, select

from packages.ai.mock_provider import MockAIProvider
from packages.risk_engine.scoring import default_scoring_config
from packages.shared.ai_service import (
    create_pending_run,
    execute_control_gap_analysis,
    execute_emerging_risk_scan,
    execute_executive_summary,
    execute_market_analysis,
    execute_risk_analysis,
)
from packages.shared.db import get_session_factory
from packages.shared.emerging_risk_service import ingest_signals, transition_candidate, triage_signal
from packages.shared.import_service import find_owner, get_or_create_category, row_to_inputs
from packages.shared.importing.mapping import DEFAULT_RISK_REGISTER_MAPPING, build_import_rows
from packages.shared.importing.parser import parse_rows
from packages.shared.models.action import Action, ActionPriority, ActionStatus
from packages.shared.models.ai import AICapability, AIRun
from packages.shared.models.control import (
    Control,
    ControlAutomation,
    ControlStatus,
    ControlType,
    RiskControl,
)
from packages.shared.models.emerging_risk import CandidateLifecycleStatus, EmergingSignal
from packages.shared.models.identity import Role, RoleName, User, UserRole
from packages.shared.models.incident import Incident, IncidentSeverity
from packages.shared.models.issue import Issue
from packages.shared.models.risk import Risk, RiskBand, RiskCategory
from packages.shared.models.scenario import Scenario, ScenarioRisk
from packages.shared.models.scoring import ScoringConfig
from packages.shared.models.simulation import SimulationConfig, SimulationResult, SimulationRun, SimulationRunStatus
from packages.shared.models.snapshot import Snapshot, SnapshotRisk
from packages.shared.risk_service import create_risk
from packages.shared.simulation_service import params_from_config
from packages.shared.snapshot_service import serialize_risk_for_snapshot
from packages.simulations.distributions import DistributionType
from packages.simulations.engine import (
    RiskSimulationInput,
    compute_statistics,
    run_annual_loss_simulation,
    run_portfolio_simulation,
)

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


BAND_ORDER = [RiskBand.LOW, RiskBand.MODERATE, RiskBand.HIGH, RiskBand.EXTREME]

# Fabricated for this prototype: no real historical data exists (this
# database has never actually run for a month), so this baseline is
# constructed by taking each risk's *current* state and deliberately
# altering a handful of fields for specific risk_codes, each documented
# below, purely so the What Changed / Trends pages have something
# realistic-looking to demonstrate immediately. This is data fabrication in
# the same spirit as the fixture spreadsheet itself (see
# docs/architecture/00-current-state-assessment.md) — never presented as
# real history, and confined to the seed layer.
SNAPSHOT_EXCLUDED_CODES = {"RSK-1019", "RSK-1020"}  # simulate: raised since the baseline
SNAPSHOT_ESCALATE_CODE = "RSK-1002"  # fabricate one band lower a month ago -> shows as escalated now
SNAPSHOT_DOWNGRADE_CODE = "RSK-1001"  # fabricate one band higher a month ago -> shows as downgraded now
SNAPSHOT_REOPEN_CODE = "RSK-1005"  # currently closed; fabricate as open a month ago -> shows as closed now


def _shift_band(band: str | None, steps: int) -> str | None:
    if band is None:
        return None
    try:
        idx = BAND_ORDER.index(RiskBand(band))
    except ValueError:
        return band
    idx = max(0, min(len(BAND_ORDER) - 1, idx + steps))
    return BAND_ORDER[idx].value


def seed_demo_snapshot(session) -> bool:
    """Seeds one fabricated historical snapshot (~30 days ago) so What
    Changed and Trends have a real comparison point immediately after
    `docker compose up`, instead of an empty page until an admin manually
    captures one. Idempotent: does nothing if any snapshot already exists.
    """
    if session.scalar(select(func.count()).select_from(Snapshot)) or 0:
        return False

    risks = session.scalars(select(Risk).order_by(Risk.risk_code)).all()
    if not risks:
        return False

    owner_change_target = next((r for r in risks if r.risk_code == "RSK-1003"), None)
    alternate_owner = session.scalars(
        select(User).where(User.email == "risk.manager@example.com")
    ).first()

    period_end = date.today() - timedelta(days=30)
    snapshot = Snapshot(
        label="30 days ago", period_end=period_end, created_at=datetime.now(timezone.utc)
    )
    session.add(snapshot)
    session.flush()

    for risk in risks:
        if risk.risk_code in SNAPSHOT_EXCLUDED_CODES:
            continue

        frozen = serialize_risk_for_snapshot(risk, appetite_status="not_configured")
        if risk.risk_code == SNAPSHOT_ESCALATE_CODE:
            frozen["residual_band"] = _shift_band(frozen["residual_band"], -1)
        elif risk.risk_code == SNAPSHOT_DOWNGRADE_CODE:
            frozen["residual_band"] = _shift_band(frozen["residual_band"], +1)
        elif risk.risk_code == SNAPSHOT_REOPEN_CODE:
            frozen["status"] = "open"
        if owner_change_target and alternate_owner and risk.id == owner_change_target.id:
            frozen["owner_id"] = str(alternate_owner.id)

        session.add(SnapshotRisk(snapshot_id=snapshot.id, risk_id=risk.id, frozen_state=frozen))

    return True


def seed_demo_issues_and_incidents(session) -> bool:
    """Seeds two illustrative issue/incident records tied to the demo
    fixture's own narrative (the unpatched-servers risk and its weak
    scanning control). Idempotent: skips if any issue already exists."""
    if session.scalar(select(func.count()).select_from(Issue)) or 0:
        return False

    target_risk = session.scalars(
        select(Risk).where(Risk.risk_code == "RSK-1002")
    ).first()
    target_control = session.scalars(
        select(Control).where(Control.control_code == "CTRL-SEC-04")
    ).first()
    if target_risk is None:
        return False

    now = datetime.now(timezone.utc)
    session.add(
        Issue(
            issue_code="ISS-0001",
            risk_id=target_risk.id,
            control_id=target_control.id if target_control else None,
            description=(
                "Penetration test found three internet-facing servers with an unpatched "
                "critical CVE despite the automated scanning control being active."
            ),
            source="External penetration test",
            created_at=now,
            updated_at=now,
        )
    )
    session.add(
        Incident(
            incident_code="INC-0001",
            risk_id=target_risk.id,
            control_id=target_control.id if target_control else None,
            description=(
                "Automated vulnerability scanner missed a critical CVE that was "
                "subsequently exploited in a controlled test environment."
            ),
            incident_date=date.today() - timedelta(days=10),
            severity=IncidentSeverity.HIGH,
            suggests_likelihood_increase=True,
            created_at=now,
            updated_at=now,
        )
    )
    return True


# Fabricated for this prototype (same spirit as the fixture spreadsheet
# itself): these loss estimates are illustrative, not derived from any
# real actuarial analysis. The simulation *results*, however, are not
# fabricated — they're computed by running the real Milestone 6/7 engine
# against these estimates at seed time, the same code path a live run
# takes, so what the Simulation Lab and Scenarios pages show immediately
# after `docker compose up` is genuine engine output, not placeholder
# numbers.
SIMULATION_CONFIGS = {
    "RSK-1002": dict(  # Unpatched internet-facing servers
        distribution_type=DistributionType.PERT,
        loss_min=5_000, loss_most_likely=25_000, loss_max=250_000,
        annual_event_frequency=1.2, correlation_group="cyber-cluster", correlation_strength=0.6,
        iterations=10_000, seed=101,
    ),
    "RSK-1001": dict(  # Single-sourced payment processor outage
        distribution_type=DistributionType.LOGNORMAL,
        loss_min=10_000, loss_most_likely=50_000, loss_max=500_000,
        annual_event_frequency=0.8, correlation_group="cyber-cluster", correlation_strength=0.6,
        iterations=10_000, seed=102,
    ),
    "RSK-1004": dict(  # Upcoming data-residency regulation
        distribution_type=DistributionType.TRIANGULAR,
        loss_min=20_000, loss_most_likely=100_000, loss_max=1_000_000,
        annual_event_frequency=0.3, correlation_group=None, correlation_strength=None,
        iterations=10_000, seed=103,
    ),
}
SCENARIO_RISK_CODES = ("RSK-1002", "RSK-1001")


def _make_result(run: SimulationRun, stats, per_risk_contribution: dict | None = None) -> SimulationResult:
    return SimulationResult(
        run_id=run.id,
        expected_annual_loss=stats.expected_annual_loss,
        median=stats.median,
        p75=stats.p75,
        p90=stats.p90,
        p95=stats.p95,
        p99=stats.p99,
        histogram=stats.histogram,
        per_risk_contribution=per_risk_contribution,
    )


def seed_demo_simulations(session) -> bool:
    """Seeds Monte Carlo configs for a few of the fixture's own risks, each
    with an already-completed run computed by the real engine (see the
    module comment above), plus a demo scenario correlating two of them so
    the Simulation Lab and Scenarios pages both have real content
    immediately. Idempotent: skips if any SimulationConfig already
    exists."""
    if session.scalar(select(func.count()).select_from(SimulationConfig)) or 0:
        return False

    manager = session.scalars(select(User).where(User.email == "risk.manager@example.com")).first()
    if manager is None:
        return False

    now = datetime.now(timezone.utc)
    configs_by_code: dict[str, SimulationConfig] = {}
    for risk_code, params in SIMULATION_CONFIGS.items():
        risk = session.scalars(select(Risk).where(Risk.risk_code == risk_code)).first()
        if risk is None:
            continue

        config = SimulationConfig(risk_id=risk.id, created_by_id=manager.id, created_at=now, **params)
        session.add(config)
        session.flush()
        configs_by_code[risk_code] = config

        annual_losses = run_annual_loss_simulation(params_from_config(config))
        stats = compute_statistics(annual_losses)
        run = SimulationRun(
            config_id=config.id, scenario_id=None, status=SimulationRunStatus.SUCCEEDED,
            iterations_used=config.iterations, seed_used=config.seed, requested_by_id=manager.id,
            created_at=now, updated_at=now, started_at=now, completed_at=now,
        )
        session.add(run)
        session.flush()
        session.add(_make_result(run, stats))

    if not configs_by_code:
        return False

    scenario_risk_ids = [
        configs_by_code[code].risk_id for code in SCENARIO_RISK_CODES if code in configs_by_code
    ]
    if len(scenario_risk_ids) < 2:
        return True

    scenario = Scenario(
        name="Regional Cyber & Payments Disruption",
        description=(
            "A regional outage that both exposes internet-facing servers to opportunistic "
            "attack and disrupts the primary payment processor at the same time — modeled "
            "here as two risks sharing a common systemic factor, not independent events."
        ),
        created_at=now, updated_at=now,
    )
    session.add(scenario)
    session.flush()
    for risk_id in scenario_risk_ids:
        session.add(ScenarioRisk(scenario_id=scenario.id, risk_id=risk_id))

    risk_inputs = [
        RiskSimulationInput(
            risk_id=str(configs_by_code[code].risk_id),
            params=params_from_config(configs_by_code[code]),
            correlation_group=configs_by_code[code].correlation_group,
            correlation_strength=configs_by_code[code].correlation_strength,
        )
        for code in SCENARIO_RISK_CODES
        if code in configs_by_code
    ]
    portfolio = run_portfolio_simulation(risk_inputs, iterations=10_000, seed=999)
    portfolio_run = SimulationRun(
        config_id=None, scenario_id=scenario.id, status=SimulationRunStatus.SUCCEEDED,
        iterations_used=10_000, seed_used=999, requested_by_id=manager.id,
        created_at=now, updated_at=now, started_at=now, completed_at=now,
    )
    session.add(portfolio_run)
    session.flush()
    session.add(_make_result(portfolio_run, portfolio.portfolio_stats, portfolio.per_risk_contribution))

    return True


def seed_demo_ai_content(session) -> bool:
    """Seeds one AI run per capability (executive summary, risk analysis,
    control-gap analysis, emerging-risk scan, market analysis) so /ai and
    the risk detail page have real content immediately. Uses
    `MockAIProvider` directly rather than the configured provider —
    seeding must never require a live API key or network access, per
    ADR 0006's "local development and CI never require credentials"
    guarantee, regardless of whether the person running this script
    happens to have GEMINI_API_KEY set.

    RSK-1002 already has a seeded incident (see
    seed_demo_issues_and_incidents), which is exactly the kind of fact the
    mock analyzer looks for, so risk-analysis produces a genuine pending
    suggestion. RSK-1004's one linked control is deliberately seeded weak
    (design=2, operating=1 — see seed_demo_risks), so control-gap-analysis
    also produces a genuine pending suggestion, not a fabricated one.
    Idempotent: skips if any AIRun already exists.
    """
    if session.scalar(select(func.count()).select_from(AIRun)) or 0:
        return False

    manager = session.scalars(select(User).where(User.email == "risk.manager@example.com")).first()
    analysis_target = session.scalars(select(Risk).where(Risk.risk_code == "RSK-1002")).first()
    control_gap_target = session.scalars(select(Risk).where(Risk.risk_code == "RSK-1004")).first()
    if manager is None or analysis_target is None or control_gap_target is None:
        return False

    provider = MockAIProvider()

    exec_run = create_pending_run(
        session, capability=AICapability.EXECUTIVE_SUMMARY, requested_by_id=manager.id,
        input_risk_ids=[], sources={"kind": "executive_dashboard_snapshot"},
    )
    execute_executive_summary(session, provider, exec_run)

    analysis_run = create_pending_run(
        session, capability=AICapability.RISK_ANALYSIS, requested_by_id=manager.id,
        input_risk_ids=[analysis_target.id], sources={"kind": "risk_snapshot", "risk_id": str(analysis_target.id)},
    )
    execute_risk_analysis(session, provider, analysis_run, risk=analysis_target)

    control_gap_run = create_pending_run(
        session, capability=AICapability.CONTROL_GAP_ANALYSIS, requested_by_id=manager.id,
        input_risk_ids=[control_gap_target.id],
        sources={"kind": "risk_and_controls_snapshot", "risk_id": str(control_gap_target.id)},
    )
    execute_control_gap_analysis(session, provider, control_gap_run, risk=control_gap_target)

    emerging_run = create_pending_run(
        session, capability=AICapability.EMERGING_RISK_SCAN, requested_by_id=manager.id,
        input_risk_ids=[], sources={"kind": "category_coverage_snapshot"},
    )
    execute_emerging_risk_scan(session, provider, emerging_run)

    market_run = create_pending_run(
        session, capability=AICapability.MARKET_ANALYSIS, requested_by_id=manager.id,
        input_risk_ids=[], sources={"kind": "category_exposure_snapshot"},
    )
    execute_market_analysis(session, provider, market_run)

    return True


def seed_demo_emerging_risk_content(session) -> bool:
    """Ingests the fixture signal adapters and AI-triages each into a
    candidate, then walks a few of them through the full lifecycle
    (accepted, dismissed, under review) so `/emerging-risks` shows every
    outcome immediately, not just freshly-triaged pending ones. Uses
    `MockAIProvider` directly, same "never requires credentials" guarantee
    as `seed_demo_ai_content`. Idempotent: skips if any `EmergingSignal`
    already exists.
    """
    if session.scalar(select(func.count()).select_from(EmergingSignal)) or 0:
        return False

    manager = session.scalars(select(User).where(User.email == "risk.manager@example.com")).first()
    if manager is None:
        return False

    signals = ingest_signals(session)
    session.flush()

    provider = MockAIProvider()
    candidates = [c for s in signals if (c := triage_signal(session, provider, s)) is not None]
    session.flush()

    if len(candidates) >= 1:
        transition_candidate(
            session, candidates[0], new_status=CandidateLifecycleStatus.ACCEPTED,
            reviewer_id=manager.id, actor_email=manager.email,
        )
    if len(candidates) >= 2:
        transition_candidate(
            session, candidates[1], new_status=CandidateLifecycleStatus.DISMISSED,
            reviewer_id=manager.id, actor_email=manager.email,
        )
    if len(candidates) >= 3:
        transition_candidate(
            session, candidates[2], new_status=CandidateLifecycleStatus.UNDER_REVIEW,
            reviewer_id=manager.id, actor_email=manager.email,
        )

    return True


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
        snapshot_created = seed_demo_snapshot(session)
        session.commit()
        issues_incidents_created = seed_demo_issues_and_incidents(session)
        session.commit()
        simulations_created = seed_demo_simulations(session)
        session.commit()
        ai_content_created = seed_demo_ai_content(session)
        session.commit()
        emerging_risk_created = seed_demo_emerging_risk_content(session)
        session.commit()
        print(
            f"Seed complete. {created} demo risk(s) newly created "
            "(controls/actions are backfilled for existing risks too, so 0 doesn't mean nothing happened). "
            f"Historical snapshot seeded: {snapshot_created}. "
            f"Demo issue/incident seeded: {issues_incidents_created}. "
            f"Demo simulations/scenario seeded: {simulations_created}. "
            f"Demo AI content seeded: {ai_content_created}. "
            f"Demo emerging-risk content seeded: {emerging_risk_created}."
        )
    finally:
        session.close()


if __name__ == "__main__":
    run()
