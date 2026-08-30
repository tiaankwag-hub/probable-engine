from __future__ import annotations

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.shared.db import Base
from packages.shared.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class RoleName(str, enum.Enum):
    VIEWER = "viewer"
    RISK_OWNER = "risk_owner"
    CONTROL_OWNER = "control_owner"
    RISK_MANAGER = "risk_manager"
    EXECUTIVE = "executive"
    ADMINISTRATOR = "administrator"
    AUDITOR = "auditor"


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    sso_subject: Mapped[str | None] = mapped_column(String(200), unique=True, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)

    user_roles: Mapped[list["UserRole"]] = relationship(back_populates="user")


class Role(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "roles"

    name: Mapped[RoleName] = mapped_column(
        Enum(RoleName, name="role_name"), unique=True, nullable=False
    )
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)


class UserRole(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )
    department_scope: Mapped[str | None] = mapped_column(String(200), nullable=True)

    user: Mapped[User] = relationship(back_populates="user_roles")
    role: Mapped[Role] = relationship()
