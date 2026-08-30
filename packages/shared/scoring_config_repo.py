"""Loads the active ScoringConfig row from the database and converts it into
the pure `packages.risk_engine.ScoringConfigData` the scoring functions
expect (ADR 0007: configuration lives in the database, not in code).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.risk_engine.scoring import ScoringConfigData, default_scoring_config
from packages.shared.models.scoring import ScoringConfig


def _to_scoring_config_data(row: ScoringConfig) -> ScoringConfigData:
    cfg = row.config
    return ScoringConfigData(
        version=row.version,
        dimension_weights=cfg["dimension_weights"],
        band_thresholds=tuple((float(b[0]), b[1]) for b in cfg["band_thresholds"]),
        max_reduction_fraction=cfg.get("max_reduction_fraction", 0.6),
        max_control_effectiveness=cfg.get("max_control_effectiveness", 5),
    )


def get_active_scoring_config(session: Session) -> ScoringConfigData:
    row = session.scalars(
        select(ScoringConfig).where(ScoringConfig.is_active.is_(True)).order_by(
            ScoringConfig.version.desc()
        )
    ).first()
    if row is None:
        return default_scoring_config()
    return _to_scoring_config_data(row)
