"""SQLAlchemy models. Import this module (or any submodule) before calling
Base.metadata.create_all()/Alembic autogenerate so every table is registered.
"""

from packages.shared.models.action import Action, ActionPriority, ActionStatus
from packages.shared.models.audit import AuditEvent
from packages.shared.models.control import (
    Control,
    ControlAutomation,
    ControlStatus,
    ControlTest,
    ControlTestResult,
    ControlType,
    RiskControl,
)
from packages.shared.models.identity import Role, User, UserRole
from packages.shared.models.imports import ImportColumnMapping, ImportJob, ImportRowError
from packages.shared.models.jobs import BackgroundJob, JobStatus
from packages.shared.models.risk import (
    Risk,
    RiskAssessment,
    RiskCategory,
    RiskHistory,
    RiskImpactScore,
)
from packages.shared.models.risk_appetite import RiskAppetite
from packages.shared.models.scoring import ScoringConfig

__all__ = [
    "Action",
    "ActionPriority",
    "ActionStatus",
    "AuditEvent",
    "Role",
    "User",
    "UserRole",
    "ImportColumnMapping",
    "ImportJob",
    "ImportRowError",
    "BackgroundJob",
    "JobStatus",
    "Control",
    "ControlAutomation",
    "ControlStatus",
    "ControlTest",
    "ControlTestResult",
    "ControlType",
    "RiskControl",
    "Risk",
    "RiskAssessment",
    "RiskCategory",
    "RiskHistory",
    "RiskImpactScore",
    "RiskAppetite",
    "ScoringConfig",
]
