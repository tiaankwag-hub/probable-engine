"""milestone 9 emerging risk radar

Revision ID: 91803297290a
Revises: 4802c89d5033
Create Date: 2026-08-31 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '91803297290a'
down_revision: Union[str, None] = '4802c89d5033'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'emerging_signals',
        sa.Column('source_adapter', sa.String(length=100), nullable=False),
        sa.Column('source_citation', sa.String(length=500), nullable=False),
        sa.Column('raw_content', sa.Text(), nullable=False),
        sa.Column('classification', sa.String(length=200), nullable=True),
        sa.Column('ingested_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_citation', name='uq_emerging_signal_source_citation'),
    )
    op.create_table(
        'emerging_risk_candidates',
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('category_id', sa.UUID(), nullable=True),
        sa.Column('relevance_assessment', sa.Text(), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=True),
        sa.Column(
            'lifecycle_status',
            sa.Enum(
                'CANDIDATE', 'UNDER_REVIEW', 'ACCEPTED', 'LINKED_TO_EXISTING', 'DISMISSED',
                name='candidate_lifecycle_status',
            ),
            nullable=False,
        ),
        sa.Column('matched_risk_id', sa.UUID(), nullable=True),
        sa.Column('created_risk_id', sa.UUID(), nullable=True),
        sa.Column('reviewed_by_id', sa.UUID(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['category_id'], ['risk_categories.id']),
        sa.ForeignKeyConstraint(['matched_risk_id'], ['risks.id']),
        sa.ForeignKeyConstraint(['created_risk_id'], ['risks.id']),
        sa.ForeignKeyConstraint(['reviewed_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'emerging_candidate_signals',
        sa.Column('candidate_id', sa.UUID(), nullable=False),
        sa.Column('signal_id', sa.UUID(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(['candidate_id'], ['emerging_risk_candidates.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['signal_id'], ['emerging_signals.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('candidate_id', 'signal_id', name='uq_emerging_candidate_signal'),
    )


def downgrade() -> None:
    op.drop_table('emerging_candidate_signals')
    op.drop_table('emerging_risk_candidates')
    op.drop_table('emerging_signals')
    sa.Enum(name='candidate_lifecycle_status').drop(op.get_bind(), checkfirst=True)
