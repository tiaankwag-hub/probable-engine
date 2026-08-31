"""additional ai capabilities: control gap analysis, emerging risk scan, market analysis

Revision ID: 4802c89d5033
Revises: cf3d102ab2b6
Create Date: 2026-08-31 21:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '4802c89d5033'
down_revision: Union[str, None] = 'cf3d102ab2b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # New AI capabilities alongside executive_summary/risk_analysis. Postgres
    # has no "ADD VALUE IF NOT EXISTS ... in one statement per value" form
    # portable across versions here, so three separate ALTER TYPE statements.
    op.execute("ALTER TYPE ai_capability ADD VALUE IF NOT EXISTS 'CONTROL_GAP_ANALYSIS'")
    op.execute("ALTER TYPE ai_capability ADD VALUE IF NOT EXISTS 'EMERGING_RISK_SCAN'")
    op.execute("ALTER TYPE ai_capability ADD VALUE IF NOT EXISTS 'MARKET_ANALYSIS'")

    # A "new_risk" suggestion (from an emerging-risk scan) has no existing
    # risk to attach to yet, unlike every other suggestion type today.
    op.alter_column('ai_suggestions', 'risk_id', existing_type=sa.UUID(), nullable=True)


def downgrade() -> None:
    # Postgres cannot drop a single enum value without recreating the type
    # and every column/constraint that depends on it; not worth it for a
    # prototype where these capabilities are additive, non-destructive
    # extensions. ai_suggestions.risk_id reverting to NOT NULL would also
    # fail outright if any 'new_risk' suggestion (risk_id IS NULL) has been
    # created since upgrading, so this migration is intentionally
    # upgrade-only.
    pass
