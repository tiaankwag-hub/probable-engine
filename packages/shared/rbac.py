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

ROLE_PERMISSIONS: dict[RoleName, frozenset[Permission]] = {
    RoleName.VIEWER: frozenset({VIEW_RISKS}),
    RoleName.RISK_OWNER: frozenset({VIEW_RISKS, CREATE_OWN_RISK, EDIT_OWN_RISK}),
    RoleName.CONTROL_OWNER: frozenset({VIEW_RISKS}),
    RoleName.RISK_MANAGER: frozenset(
        {VIEW_RISKS, CREATE_OWN_RISK, EDIT_OWN_RISK, EDIT_ANY_RISK, RUN_IMPORTS}
    ),
    RoleName.EXECUTIVE: frozenset({VIEW_RISKS}),
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
        }
    ),
    RoleName.AUDITOR: frozenset({VIEW_RISKS, READ_AUDIT_LOG}),
}


def roles_granting(permission: Permission) -> set[RoleName]:
    return {role for role, perms in ROLE_PERMISSIONS.items() if permission in perms}


def role_has_permission(role: RoleName, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, frozenset())


def any_role_has_permission(roles: set[RoleName], permission: Permission) -> bool:
    return any(role_has_permission(role, permission) for role in roles)
