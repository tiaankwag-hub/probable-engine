"""Pure RBAC data: the permission matrix from docs/api/00-api-design.md,
expressed as code so `apps/api` can enforce it and the role/access test
suite can assert against the same source of truth. No FastAPI/HTTP
concerns here — see apps/api/app/deps.py for the request-level dependency
that uses this module.
"""

from __future__ import annotations

from packages.shared.models.identity import RoleName

Permission = str

VIEW_RISKS: Permission = "view_risks"
CREATE_OWN_RISK: Permission = "create_own_risk"
EDIT_OWN_RISK: Permission = "edit_own_risk"
EDIT_ANY_RISK: Permission = "edit_any_risk"
RUN_IMPORTS: Permission = "run_imports"
MANAGE_USERS: Permission = "manage_users"
READ_AUDIT_LOG: Permission = "read_audit_log"
MANAGE_SCORING_CONFIG: Permission = "manage_scoring_config"

CREATE_CONTROL: Permission = "create_control"
MANAGE_OWN_CONTROL: Permission = "manage_own_control"
MANAGE_ANY_CONTROL: Permission = "manage_any_control"

CREATE_ACTION: Permission = "create_action"
EDIT_OWN_ACTION: Permission = "edit_own_action"
EDIT_ANY_ACTION: Permission = "edit_any_action"

MANAGE_APPETITE: Permission = "manage_appetite"

MANAGE_SNAPSHOTS: Permission = "manage_snapshots"
CREATE_ISSUE: Permission = "create_issue"
CREATE_INCIDENT: Permission = "create_incident"
TRIGGER_INCIDENT_REVIEW: Permission = "trigger_incident_review"

GENERATE_REPORTS: Permission = "generate_reports"
VIEW_REPORT_RUNS: Permission = "view_report_runs"

RUN_OWN_SIMULATION: Permission = "run_own_simulation"
RUN_ANY_SIMULATION: Permission = "run_any_simulation"
VIEW_SIMULATION_RESULTS: Permission = "view_simulation_results"
MANAGE_SCENARIOS: Permission = "manage_scenarios"

REQUEST_OWN_AI_ANALYSIS: Permission = "request_own_ai_analysis"
REQUEST_ANY_AI_ANALYSIS: Permission = "request_any_ai_analysis"
REQUEST_EXECUTIVE_SUMMARY: Permission = "request_executive_summary"
APPROVE_AI_SUGGESTIONS: Permission = "approve_ai_suggestions"

ROLE_PERMISSIONS: dict[RoleName, frozenset[Permission]] = {
    RoleName.VIEWER: frozenset({VIEW_RISKS}),
    RoleName.RISK_OWNER: frozenset(
        {
            VIEW_RISKS,
            CREATE_OWN_RISK,
            EDIT_OWN_RISK,
            CREATE_ACTION,
            EDIT_OWN_ACTION,
            CREATE_ISSUE,
            CREATE_INCIDENT,
            RUN_OWN_SIMULATION,
            VIEW_SIMULATION_RESULTS,
            REQUEST_OWN_AI_ANALYSIS,
        }
    ),
    RoleName.CONTROL_OWNER: frozenset(
        {
            VIEW_RISKS,
            CREATE_CONTROL,
            MANAGE_OWN_CONTROL,
            CREATE_ACTION,
            EDIT_OWN_ACTION,
            CREATE_ISSUE,
            CREATE_INCIDENT,
        }
    ),
    RoleName.RISK_MANAGER: frozenset(
        {
            VIEW_RISKS,
            CREATE_OWN_RISK,
            EDIT_OWN_RISK,
            EDIT_ANY_RISK,
            RUN_IMPORTS,
            CREATE_CONTROL,
            MANAGE_ANY_CONTROL,
            CREATE_ACTION,
            EDIT_ANY_ACTION,
            MANAGE_SNAPSHOTS,
            CREATE_ISSUE,
            CREATE_INCIDENT,
            TRIGGER_INCIDENT_REVIEW,
            GENERATE_REPORTS,
            VIEW_REPORT_RUNS,
            RUN_ANY_SIMULATION,
            VIEW_SIMULATION_RESULTS,
            MANAGE_SCENARIOS,
            REQUEST_ANY_AI_ANALYSIS,
            REQUEST_EXECUTIVE_SUMMARY,
            APPROVE_AI_SUGGESTIONS,
        }
    ),
    RoleName.EXECUTIVE: frozenset(
        {
            VIEW_RISKS, GENERATE_REPORTS, VIEW_REPORT_RUNS, VIEW_SIMULATION_RESULTS,
            REQUEST_EXECUTIVE_SUMMARY,
        }
    ),
    RoleName.ADMINISTRATOR: frozenset(
        {
            VIEW_RISKS,
            CREATE_OWN_RISK,
            EDIT_OWN_RISK,
            EDIT_ANY_RISK,
            RUN_IMPORTS,
            MANAGE_USERS,
            READ_AUDIT_LOG,
            MANAGE_SCORING_CONFIG,
            CREATE_CONTROL,
            MANAGE_ANY_CONTROL,
            CREATE_ACTION,
            EDIT_ANY_ACTION,
            MANAGE_APPETITE,
            MANAGE_SNAPSHOTS,
            CREATE_ISSUE,
            CREATE_INCIDENT,
            TRIGGER_INCIDENT_REVIEW,
            GENERATE_REPORTS,
            VIEW_REPORT_RUNS,
            RUN_ANY_SIMULATION,
            VIEW_SIMULATION_RESULTS,
            MANAGE_SCENARIOS,
            REQUEST_ANY_AI_ANALYSIS,
            REQUEST_EXECUTIVE_SUMMARY,
            APPROVE_AI_SUGGESTIONS,
        }
    ),
    RoleName.AUDITOR: frozenset({VIEW_RISKS, READ_AUDIT_LOG, VIEW_REPORT_RUNS}),
}


def roles_granting(permission: Permission) -> set[RoleName]:
    return {role for role, perms in ROLE_PERMISSIONS.items() if permission in perms}


def role_has_permission(role: RoleName, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, frozenset())


def any_role_has_permission(roles: set[RoleName], permission: Permission) -> bool:
    return any(role_has_permission(role, permission) for role in roles)
