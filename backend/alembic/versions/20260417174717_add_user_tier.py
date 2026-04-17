"""add user tier

Revision ID: 20260417174717
Revises: 20260417000000
Create Date: 2026-04-17 17:47:17

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260417174717'
down_revision = '20260417000000'
branch_labels = None
depends_on = None


def upgrade():
    # Add tier column to users table
    op.add_column('users', sa.Column('tier', sa.String(), nullable=False, server_default='free'))


def downgrade():
    # Remove tier column from users table
    op.drop_column('users', 'tier')
