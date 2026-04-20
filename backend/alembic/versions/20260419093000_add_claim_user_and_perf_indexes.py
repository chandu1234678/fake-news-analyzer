"""add claim user and performance indexes

Revision ID: 20260419093000
Revises: 20260417174717
Create Date: 2026-04-19 09:30:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260419093000'
down_revision = '20260417174717'
branch_labels = None
depends_on = None


def upgrade():
    # Add claim owner for user analytics and quota queries
    op.add_column('claim_records', sa.Column('user_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_claim_records_user_id_users',
        'claim_records',
        'users',
        ['user_id'],
        ['id'],
    )

    # Composite indexes for hot time-based queries
    op.create_index('ix_claim_records_user_created', 'claim_records', ['user_id', 'created_at'], unique=False)
    op.create_index('ix_user_feedback_user_created', 'user_feedback', ['user_id', 'created_at'], unique=False)


def downgrade():
    op.drop_index('ix_user_feedback_user_created', table_name='user_feedback')
    op.drop_index('ix_claim_records_user_created', table_name='claim_records')
    op.drop_constraint('fk_claim_records_user_id_users', 'claim_records', type_='foreignkey')
    op.drop_column('claim_records', 'user_id')
