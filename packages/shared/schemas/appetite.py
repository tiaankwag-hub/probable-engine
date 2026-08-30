from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.risk_engine.appetite import BAND_RANK


class RiskAppetiteIn(BaseModel):
    category_id: uuid.UUID | None = None
    business_unit: str | None = None
    appetite_band: str
    tolerance_band: str
    limit_value: float | None = Field(default=None, ge=0)
    effective_from: date
    effective_to: date | None = None

    @model_validator(mode="after")
    def check_bands(self) -> "RiskAppetiteIn":
        for field_name in ("appetite_band", "tolerance_band"):
            value = getattr(self, field_name)
            if value not in BAND_RANK:
                raise ValueError(f"{field_name} must be one of {sorted(BAND_RANK)}")
        if BAND_RANK[self.tolerance_band] < BAND_RANK[self.appetite_band]:
            raise ValueError("tolerance_band must be at or above appetite_band")
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to must be on or after effective_from")
        return self


class RiskAppetiteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category_id: uuid.UUID | None
    business_unit: str | None
    appetite_band: str
    tolerance_band: str
    limit_value: float | None
    effective_from: date
    effective_to: date | None
