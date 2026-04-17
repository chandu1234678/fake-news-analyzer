"""add ab testing tables

Revision ID: 20260417000000
Revises: 20260416220000
Create Date: 2026-04-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260417000000'
down_revision = '20260416220000'
branch_labels = None
depends_on = None


def upgrade():
    # Create ab_tests table
    op.create_table(
        'ab_tests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('variants', sa.Text(), nullable=False),
        sa.Column('traffic_split', sa.Text(), nullable=False),
        sa.Column('metrics', sa.Text(), nullable=True),
        sa.Column('start_date', sa.DateTime(), nullable=True),
        sa.Column('end_date', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ab_tests_name'), 'ab_tests', ['name'], unique=True)
    op.create_index(op.f('ix_ab_tests_status'), 'ab_tests', ['status'], unique=False)
    op.create_index(op.f('ix_ab_tests_start_date'), 'ab_tests', ['start_date'], unique=False)
    op.create_index(op.f('ix_ab_tests_end_date'), 'ab_tests', ['end_date'], unique=False)

    # Create ab_test_assignments table
    op.create_table(
        'ab_test_assignments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('test_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('session_key', sa.String(), nullable=True),
        sa.Column('variant', sa.String(), nullable=False),
        sa.Column('assigned_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['test_id'], ['ab_tests.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ab_test_assignments_test_id'), 'ab_test_assignments', ['test_id'], unique=False)
    op.create_index(op.f('ix_ab_test_assignments_user_id'), 'ab_test_assignments', ['user_id'], unique=False)
    op.create_index(op.f('ix_ab_test_assignments_session_key'), 'ab_test_assignments', ['session_key'], unique=False)
    op.create_index(op.f('ix_ab_test_assignments_variant'), 'ab_test_assignments', ['variant'], unique=False)
    op.create_index(op.f('ix_ab_test_assignments_assigned_at'), 'ab_test_assignments', ['assigned_at'], unique=False)
    op.create_index('ix_ab_assignments_test_user', 'ab_test_assignments', ['test_id', 'user_id'], unique=False)
    op.create_index('ix_ab_assignments_test_session', 'ab_test_assignments', ['test_id', 'session_key'], unique=False)

    # Create ab_test_events table
    op.create_table(
        'ab_test_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('test_id', sa.Integer(), nullable=False),
        sa.Column('assignment_id', sa.Integer(), nullable=True),
        sa.Column('variant', sa.String(), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('event_data', sa.Text(), nullable=True),
        sa.Column('accuracy', sa.Float(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['test_id'], ['ab_tests.id'], ),
        sa.ForeignKeyConstraint(['assignment_id'], ['ab_test_assignments.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ab_test_events_test_id'), 'ab_test_events', ['test_id'], unique=False)
    op.create_index(op.f('ix_ab_test_events_assignment_id'), 'ab_test_events', ['assignment_id'], unique=False)
    op.create_index(op.f('ix_ab_test_events_variant'), 'ab_test_events', ['variant'], unique=False)
    op.create_index(op.f('ix_ab_test_events_event_type'), 'ab_test_events', ['event_type'], unique=False)
    op.create_index(op.f('ix_ab_test_events_created_at'), 'ab_test_events', ['created_at'], unique=False)
    op.create_index('ix_ab_events_test_variant', 'ab_test_events', ['test_id', 'variant'], unique=False)
    op.create_index('ix_ab_events_test_type', 'ab_test_events', ['test_id', 'event_type'], unique=False)


def downgrade():
    op.drop_index('ix_ab_events_test_type', table_name='ab_test_events')
    op.drop_index('ix_ab_events_test_variant', table_name='ab_test_events')
    op.drop_index(op.f('ix_ab_test_events_created_at'), table_name='ab_test_events')
    op.drop_index(op.f('ix_ab_test_events_event_type'), table_name='ab_test_events')
    op.drop_index(op.f('ix_ab_test_events_variant'), table_name='ab_test_events')
    op.drop_index(op.f('ix_ab_test_events_assignment_id'), table_name='ab_test_events')
    op.drop_index(op.f('ix_ab_test_events_test_id'), table_name='ab_test_events')
    op.drop_table('ab_test_events')
    
    op.drop_index('ix_ab_assignments_test_session', table_name='ab_test_assignments')
    op.drop_index('ix_ab_assignments_test_user', table_name='ab_test_assignments')
    op.drop_index(op.f('ix_ab_test_assignments_assigned_at'), table_name='ab_test_assignments')
    op.drop_index(op.f('ix_ab_test_assignments_variant'), table_name='ab_test_assignments')
    op.drop_index(op.f('ix_ab_test_assignments_session_key'), table_name='ab_test_assignments')
    op.drop_index(op.f('ix_ab_test_assignments_user_id'), table_name='ab_test_assignments')
    op.drop_index(op.f('ix_ab_test_assignments_test_id'), table_name='ab_test_assignments')
    op.drop_table('ab_test_assignments')
    
    op.drop_index(op.f('ix_ab_tests_end_date'), table_name='ab_tests')
    op.drop_index(op.f('ix_ab_tests_start_date'), table_name='ab_tests')
    op.drop_index(op.f('ix_ab_tests_status'), table_name='ab_tests')
    op.drop_index(op.f('ix_ab_tests_name'), table_name='ab_tests')
    op.drop_table('ab_tests')
