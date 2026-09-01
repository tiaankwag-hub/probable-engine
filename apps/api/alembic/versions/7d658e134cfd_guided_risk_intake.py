"""guided risk intake

Revision ID: 7d658e134cfd
Revises: 91803297290a
Create Date: 2026-09-01 23:26:54.285378

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '7d658e134cfd'
down_revision: Union[str, None] = '91803297290a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'risk_intake_sessions',
        sa.Column('initiated_by_id', sa.UUID(), nullable=False),
        sa.Column(
            'status',
            sa.Enum('IN_PROGRESS', 'READY_TO_SUBMIT', 'SUBMITTED', 'ABANDONED', name='intake_session_status'),
            nullable=False,
        ),
        sa.Column('transcript', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('draft_fields', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('turn_count', sa.Integer(), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=True),
        sa.Column('resulting_risk_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['initiated_by_id'], ['users.id']),
        sa.ForeignKeyConstraint(['resulting_risk_id'], ['risks.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('risk_intake_sessions')
    sa.Enum(name='intake_session_status').drop(op.get_bind(), checkfirst=True)
