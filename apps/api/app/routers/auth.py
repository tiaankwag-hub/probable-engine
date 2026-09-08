"""Auth routes. `/me` is mode-independent — it works the same whether the
caller authenticated via mock-login or a real IAP assertion, since it just
reflects whatever `get_current_user` resolved. `/mock-login` is the
opposite: a deliberate local dev/CI backdoor (ADR 0010) that mints a valid
token for any seeded email with no password and no verification. It lives
in its own router (`mock_login_router`) so `apps/api/app/main.py` can leave
it out of the route table entirely when `auth_mode != "mock"` — not
disabled, not gated by a check that could be missed, genuinely absent.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.deps import CurrentUser, get_current_user, get_db
from packages.shared.models.identity import User, UserRole
from packages.shared.schemas.auth import CurrentUserOut, MockLoginIn, MockLoginOut

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
mock_login_router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@mock_login_router.post("/mock-login", response_model=MockLoginOut)
def mock_login(payload: MockLoginIn, db: Session = Depends(get_db)):
    user = db.scalars(select(User).where(User.email == payload.email)).first()
    if user is None or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unknown user")

    role_rows = db.scalars(select(UserRole).where(UserRole.user_id == user.id)).all()
    roles = sorted({ur.role.name.value for ur in role_rows})

    return MockLoginOut(
        access_token=str(user.id),
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        roles=roles,
    )


@router.get("/me", response_model=CurrentUserOut)
def whoami(current_user: CurrentUser = Depends(get_current_user)):
    """Resolves whatever the caller authenticated as to an identity and
    role list — the same lookup every other route already does via
    `get_current_user`, just exposed directly. This is what lets a client
    holding nothing but a token/assertion (the MCP gateway, in particular —
    see ADR 0009) confirm who it's acting as without a separate, more-
    permissive credential or a duplicate identity-resolution path.
    """
    return CurrentUserOut(
        user_id=current_user.user.id,
        email=current_user.email,
        display_name=current_user.user.display_name,
        roles=sorted(r.value for r in current_user.roles),
    )
