"""Add scheduled_jobs table for Option 2 - AutoPilot Scheduler

Revision ID: 005_add_scheduled_jobs_table
Revises: 004_phase35_job_fields
Create Date: 2024-11-02 23:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005_add_scheduled_jobs_table'
down_revision = '004_phase35_job_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create scheduled_jobs table
    op.create_table(
        'scheduled_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('site_id', sa.Integer(), nullable=False),
        sa.Column('license_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('context', sa.Text(), nullable=True),
        sa.Column('goal', sa.String(), nullable=True),
        sa.Column('publish_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('user_images', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('generate_images', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('job_id', sa.Integer(), nullable=True),
        sa.Column('article_id', sa.Integer(), nullable=True),
        sa.Column('wordpress_post_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['site_id'], ['sites.id'], ),
        sa.ForeignKeyConstraint(['license_id'], ['licenses.id'], ),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
        sa.ForeignKeyConstraint(['article_id'], ['articles.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scheduled_jobs_id'), 'scheduled_jobs', ['id'], unique=False)
    op.create_index('ix_scheduled_jobs_site_id', 'scheduled_jobs', ['site_id'], unique=False)
    op.create_index('ix_scheduled_jobs_publish_date', 'scheduled_jobs', ['publish_date'], unique=False)
    op.create_index('ix_scheduled_jobs_status', 'scheduled_jobs', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_scheduled_jobs_status', table_name='scheduled_jobs')
    op.drop_index('ix_scheduled_jobs_publish_date', table_name='scheduled_jobs')
    op.drop_index('ix_scheduled_jobs_site_id', table_name='scheduled_jobs')
    op.drop_index(op.f('ix_scheduled_jobs_id'), table_name='scheduled_jobs')
    op.drop_table('scheduled_jobs')

