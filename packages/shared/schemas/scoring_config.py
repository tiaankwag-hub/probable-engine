from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.risk_engine.scoring import DIMENSIONS


class ScoringConfigIn(BaseModel):
    dimension_weights: dict[str, float]
    band_thresholds: list[tuple[float, str]] = Field(min_length=1)
    max_reduction_fraction: float = Field(gt=0, le=1)
    max_control_effectiveness: int = Field(ge=1, le=10)

    @model_validator(mode="after")
    def check_weights(self) -> "ScoringConfigIn":
        missing = set(DIMENSIONS) - set(self.dimension_weights)
        if missing:
            raise ValueError(f"missing weights for dimensions: {sorted(missing)}")
        total = sum(self.dimension_weights.values())
        if not (0.999 <= total <= 1.001):
            raise ValueError(f"dimension weights must sum to 1.0, got {total}")
        bounds = [b for b, _ in self.band_thresholds]
        if bounds != sorted(bounds):
            raise ValueError("band_thresholds must be sorted ascending by upper bound")
        return self


class ScoringConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    dimension_weights: dict[str, float]
    band_thresholds: list[tuple[float, str]]
    max_reduction_fraction: float
    max_control_effectiveness: int
    is_active: bool
    created_at: datetime

    @classmethod
    def from_model(cls, row) -> "ScoringConfigOut":
        cfg = row.config
        return cls(
            id=row.id,
            version=row.version,
            dimension_weights=cfg["dimension_weights"],
            band_thresholds=[tuple(t) for t in cfg["band_thresholds"]],
            max_reduction_fraction=cfg.get("max_reduction_fraction", 0.6),
            max_control_effectiveness=cfg.get("max_control_effectiveness", 5),
            is_active=row.is_active,
            created_at=row.created_at,
        )
