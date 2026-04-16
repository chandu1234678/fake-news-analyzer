"""add_clustering_fields

Revision ID: 20260416220000
Revises: 20260416214009
Create Date: 2026-04-16 22:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260416220000'
down_revision = '20260416214009'
branch_labels = None
depends_on = None


def upgrade():
    # Add clustering and social graph fields to velocity_records
    op.add_column('velocity_records', sa.Column('cluster_id', sa.Integer(), nullable=True))
    op.add_column('velocity_records', sa.Column('cluster_size', sa.Integer(), nullable=True))
    op.add_column('velocity_records', sa.Column('campaign_score', sa.Float(), nullable=True))
    op.add_column('velocity_records', sa.Column('is_coordinated', sa.Boolean(), nullable=True, server_default='false'))
    
    # Create indexes
    op.create_index('ix_velocity_records_cluster_id', 'velocity_records', ['cluster_id'])
    op.create_index('ix_velocity_records_is_coordinated', 'velocity_records', ['is_coordinated'])
    op.create_index('ix_velocity_records_coordinated', 'velocity_records', ['is_coordinated', 'created_at'])


def downgrade():
    # Drop indexes
    op.drop_index('ix_velocity_records_coordinated', table_name='velocity_records')
    op.drop_index('ix_velocity_records_is_coordinated', table_name='velocity_records')
    op.drop_index('ix_velocity_records_cluster_id', table_name='velocity_records')
    
    # Drop columns
    op.drop_column('velocity_records', 'is_coordinated')
    op.drop_column('velocity_records', 'campaign_score')
    op.drop_column('velocity_records', 'cluster_size')
    op.drop_column('velocity_records', 'cluster_id')
