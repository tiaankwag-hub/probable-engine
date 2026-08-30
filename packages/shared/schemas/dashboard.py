from __future__ import annotations

import uuid

from pydantic import BaseModel


class BandCount(BaseModel):
    band: str
    count: int


class CategoryExposure(BaseModel):
    category_id: uuid.UUID | None
    category_name: str
    risk_count: int
    avg_residual_score: float | None


class VelocityCount(BaseModel):
    velocity: str
    count: int


class HeatmapCell(BaseModel):
    likelihood: int
    impact: int
    count: int
    dominant_band: str | None


class TopRiskSummary(BaseModel):
    id: uuid.UUID
    risk_code: str
    title: str
    category_name: str | None
    residual_score: float | None
    residual_band: str | None
    owner_email: str | None
    next_review_date: str | None


class ExecutiveDashboard(BaseModel):
    total_risks: int
    extreme_count: int
    high_count: int
    moderate_count: int
    low_count: int
    unscored_count: int
    overdue_reviews_count: int
    band_distribution: list[BandCount]
    category_exposure: list[CategoryExposure]
    velocity_distribution: list[VelocityCount]
    heatmap: list[HeatmapCell]
    top_risks: list[TopRiskSummary]
