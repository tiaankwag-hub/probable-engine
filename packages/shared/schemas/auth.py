from __future__ import annotations

import uuid

from pydantic import BaseModel, EmailStr


class MockLoginIn(BaseModel):
    email: EmailStr


class MockLoginOut(BaseModel):
    access_token: str
    user_id: uuid.UUID
    email: str
    display_name: str
    roles: list[str]
