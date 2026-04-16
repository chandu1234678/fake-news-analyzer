"""add_velocity_tracking

Revision ID: 20260416214009
Revises: 
Create Date: 2026-04-16 21:40:09

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260416214009'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create velocity_records table
    op.create_table(
        'velocity_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('claim_hash', sa.String(length=64), nullable=False),
        sa.Column('claim_text', sa.Text(), nullable=False),
        sa.Column('velocity_score', sa.Float(), nullable=False),
        sa.Column('count_5min', sa.Integer(), nullable=False),
        sa.Column('count_1hr', sa.Integer(), nullable=False),
        sa.Column('count_24hr', sa.Integer(), nullable=False),
        sa.Column('is_viral', sa.Boolean(), nullable=True),
        sa.Column('is_trending', sa.Boolean(), nullable=True),
        sa.Column('cooldown_score', sa.Float(), nullable=True),
        sa.Column('cooldown_level', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('ix_velocity_records_claim_hash', 'velocity_records', ['claim_hash'])
    op.create_index('ix_velocity_records_is_viral', 'velocity_records', ['is_viral'])
    op.create_index('ix_velocity_records_is_trending', 'velocity_records', ['is_trending'])
    op.create_index('ix_velocity_records_created_at', 'velocity_records', ['created_at'])
    op.create_index('ix_velocity_records_hash_created', 'velocity_records', ['claim_hash', 'created_at'])
    op.create_index('ix_velocity_records_viral_created', 'velocity_records', ['is_viral', 'created_at'])


def downgrade():
    # Drop indexes
    op.drop_index('ix_velocity_records_viral_created', table_name='velocity_records')
    op.drop_index('ix_velocity_records_hash_created', table_name='velocity_records')
    op.drop_index('ix_velocity_records_created_at', table_name='velocity_records')
    op.drop_index('ix_velocity_records_is_trending', table_name='velocity_records')
    op.drop_index('ix_velocity_records_is_viral', table_name='velocity_records')
    op.drop_index('ix_velocity_records_claim_hash', table_name='velocity_records')
    
    # Drop table
    op.drop_table('velocity_records')
