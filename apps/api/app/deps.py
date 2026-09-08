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
from apps.api.app.iap_auth import IAPVerificationError, verify_iap_assertion
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


def _load_current_user(db: Session, *, user_id: uuid.UUID | None, email: str | None) -> CurrentUser:
    """Common tail of both auth modes: resolve a `User` row (by whichever
    identifier that mode trusts) and its roles. Neither caller may supply
    a role directly — roles always come from `user_roles`, never a claim
    the client sent (ADR 0010)."""
    user = db.get(User, user_id) if user_id is not None else db.scalars(
        select(User).where(User.email == email)
    ).first()
    if user is None or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unknown user")

    role_rows = db.scalars(select(UserRole).where(UserRole.user_id == user.id)).all()
    roles = {ur.role.name for ur in role_rows}
    return CurrentUser(user=user, roles=roles)


def _get_current_user_mock(authorization: str | None, db: Session) -> CurrentUser:
    """Local dev/CI only (ADR 0010). The bearer token is the user's raw
    UUID — no signature, no expiry, no verification of any kind. Anyone
    who knows or guesses a UUID can act as that user. This function must
    never run when `Settings.auth_mode != "mock"` — see get_current_user."""
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
    return _load_current_user(db, user_id=user_id, email=None)


def _get_current_user_iap(
    x_goog_iap_jwt_assertion: str | None,
    authorization: str | None,
    settings: Settings,
    db: Session,
) -> CurrentUser:
    """Production (ADR 0010). Two sources of a Google-signed ID token are
    accepted, verified identically either way — the important thing is
    that the token is genuinely signed by Google for this exact audience,
    not which header carried it:

    - `X-Goog-IAP-JWT-Assertion`: what IAP itself injects for every
      browser request that reaches this service through the load
      balancer (see infra/environments/production/iap.tf). IAP strips any
      client-supplied copy of this header first, so its mere presence
      already means "this came through IAP" — but the signature and
      audience are still verified on every call rather than trusted
      alone.
    - `Authorization: Bearer <token>`: for callers that never go through
      IAP at all — chiefly the MCP gateway (ADR 0009), whose
      RiskPlatformTokenVerifier forwards whatever the MCP client
      presented. In production that token is expected to be a Google ID
      token minted for this same audience (e.g. via
      `gcloud auth print-identity-token --audiences=<IAP_AUDIENCE>` — see
      the deployment runbook), not an IAP session artifact; the
      verification call is identical either way because both really are
      just Google-signed JWTs for one audience.
    """
    if not settings.iap_audience:
        # A misconfiguration, not a caller error: refuse closed rather than
        # silently accepting unverifiable assertions.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="auth_mode=iap but IAP_AUDIENCE is not configured",
        )
    assertion = x_goog_iap_jwt_assertion or (
        authorization.removeprefix("Bearer ").strip()
        if authorization and authorization.startswith("Bearer ")
        else None
    )
    try:
        email = verify_iap_assertion(assertion or "", settings.iap_audience)
    except IAPVerificationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return _load_current_user(db, user_id=None, email=email)


def get_current_user(
    authorization: str | None = Header(default=None),
    x_goog_iap_jwt_assertion: str | None = Header(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    if settings.auth_mode == "iap":
        return _get_current_user_iap(x_goog_iap_jwt_assertion, authorization, settings, db)
    return _get_current_user_mock(authorization, db)


def require_permission(permission: Permission):
    def _dependency(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not any_role_has_permission(current_user.roles, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"missing required permission: {permission}",
            )
        return current_user

    return _dependency
