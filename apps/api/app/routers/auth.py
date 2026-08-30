"""Mock authentication for local development and tests (ADR 0010). NOT a
production auth mechanism — see apps/api/app/deps.py for the caveats.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.app.deps import get_db
from packages.shared.models.identity import User, UserRole
from packages.shared.schemas.auth import MockLoginIn, MockLoginOut

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/mock-login", response_model=MockLoginOut)
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
