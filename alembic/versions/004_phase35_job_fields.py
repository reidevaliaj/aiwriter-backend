"""Phase 3.5: Add context, user_images, FAQ, CTA, template, style_preset to jobs

Revision ID: 004_phase35_job_fields
Revises: 003_phase3_article_fields
Create Date: 2024-11-01 18:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '004_phase35_job_fields'
down_revision = '003_phase3_article_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add Phase 3.5 fields to jobs table
    op.add_column('jobs', sa.Column('context', sa.Text(), nullable=True))
    op.add_column('jobs', sa.Column('user_images', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('jobs', sa.Column('include_faq', sa.Boolean(), server_default=sa.text('true'), nullable=False))
    op.add_column('jobs', sa.Column('include_cta', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.add_column('jobs', sa.Column('cta_url', sa.String(), nullable=True))
    op.add_column('jobs', sa.Column('template', sa.String(), server_default='classic', nullable=False))
    op.add_column('jobs', sa.Column('style_preset', sa.String(), server_default='default', nullable=False))


def downgrade() -> None:
    op.drop_column('jobs', 'style_preset')
    op.drop_column('jobs', 'template')
    op.drop_column('jobs', 'cta_url')
    op.drop_column('jobs', 'include_cta')
    op.drop_column('jobs', 'include_faq')
    op.drop_column('jobs', 'user_images')
    op.drop_column('jobs', 'context')

