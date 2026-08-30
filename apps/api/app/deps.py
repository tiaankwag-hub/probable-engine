"""Request-scoped dependencies: DB session, mock-auth identity resolution,
and RBAC enforcement (ADR 0010). This is where the pure `packages.shared.rbac`
data becomes an actual per-request check — every route that mutates or reads
non-public data must depend on `get_current_user` and, where relevant,
`require_permission(...)`.
"""

from __future__ import annotations

import uuid
from collections.abc import Generator
from functools import lru_cache

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.config import Settings, get_settings
from packages.shared.db import get_session_factory
from packages.shared.models.identity import RoleName, User, UserRole
from packages.shared.rbac import Permission, any_role_has_permission
from packages.shared.storage import LocalFileSystemStore, ObjectStore


def get_db() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


@lru_cache
def _object_store_for_root(root: str) -> LocalFileSystemStore:
    return LocalFileSystemStore(root)


def get_object_store(settings: Settings = Depends(get_settings)) -> ObjectStore:
    return _object_store_for_root(settings.storage_root)


class CurrentUser:
    def __init__(self, user: User, roles: set[RoleName]):
        self.user = user
        self.roles = roles

    @property
    def email(self) -> str:
        return self.user.email


def get_current_user(
    authorization: str | None = Header(default=None), db: Session = Depends(get_db)
) -> CurrentUser:
    """Mock authentication for local development and tests (ADR 0010). The
    bearer token is the user's raw UUID — there is no signature, expiry, or
    encryption. This is intentionally unfit for any environment other than
    local dev/CI and is replaced by real Google IAM/IAP or corporate SSO
    verification in Milestone 11; nothing about the RBAC enforcement below
    changes when that swap happens.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token"
        )
    token = authorization.removeprefix("Bearer ").strip()
    try:
        user_id = uuid.UUID(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid bearer token"
        ) from exc

    user = db.get(User, user_id)
    if user is None or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unknown user")

    role_rows = db.scalars(
        select(UserRole).where(UserRole.user_id == user_id)
    ).all()
    roles = {ur.role.name for ur in role_rows}
    return CurrentUser(user=user, roles=roles)


def require_permission(permission: Permission):
    def _dependency(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not any_role_has_permission(current_user.roles, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"missing required permission: {permission}",
            )
        return current_user

    return _dependency
