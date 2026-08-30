from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class RiskCategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None
    description: str | None
