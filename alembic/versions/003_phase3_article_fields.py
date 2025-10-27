"""Phase 3: Add articles table and update jobs

Revision ID: 003_phase3_article_fields
Revises: 002_add_callback_url
Create Date: 2024-12-19 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003_phase3_article_fields'
down_revision = '002_add_callback_url'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create articles table
    op.create_table('articles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=False),
        sa.Column('license_id', sa.Integer(), nullable=False),
        sa.Column('topic', sa.Text(), nullable=False),
        sa.Column('language', sa.String(), nullable=False, default='de'),
        sa.Column('outline_json', sa.JSON(), nullable=True),
        sa.Column('article_html', sa.Text(), nullable=True),
        sa.Column('meta_title', sa.String(length=160), nullable=True),
        sa.Column('meta_description', sa.String(length=180), nullable=True),
        sa.Column('faq_json', sa.JSON(), nullable=True),
        sa.Column('schema_json', sa.JSON(), nullable=True),
        sa.Column('image_urls_json', sa.JSON(), nullable=True, default=[]),
        sa.Column('tokens_input', sa.Integer(), nullable=True),
        sa.Column('tokens_output', sa.Integer(), nullable=True),
        sa.Column('image_cost_cents', sa.Integer(), nullable=True, default=0),
        sa.Column('status', sa.Enum('draft', 'ready', 'failed', name='articlestatus'), nullable=False, default='ready'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
        sa.ForeignKeyConstraint(['license_id'], ['licenses.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Add indexes
    op.create_index(op.f('ix_articles_job_id'), 'articles', ['job_id'], unique=False)
    op.create_index(op.f('ix_articles_license_id'), 'articles', ['license_id'], unique=False)
    op.create_index(op.f('ix_articles_created_at'), 'articles', ['created_at'], unique=False)
    op.create_index('ix_articles_license_created', 'articles', ['license_id', 'created_at'], unique=False)
    
    # Update jobs table
    op.add_column('jobs', sa.Column('requested_images', sa.Integer(), nullable=True, default=0))
    op.add_column('jobs', sa.Column('language', sa.String(), nullable=True, default='de'))
    
    # Update existing jobs to have default values
    op.execute("UPDATE jobs SET requested_images = 0 WHERE requested_images IS NULL")
    op.execute("UPDATE jobs SET language = 'de' WHERE language IS NULL")


def downgrade() -> None:
    # Drop articles table
    op.drop_index('ix_articles_license_created', table_name='articles')
    op.drop_index(op.f('ix_articles_created_at'), table_name='articles')
    op.drop_index(op.f('ix_articles_license_id'), table_name='articles')
    op.drop_index(op.f('ix_articles_job_id'), table_name='articles')
    op.drop_table('articles')
    
    # Remove columns from jobs table
    op.drop_column('jobs', 'language')
    op.drop_column('jobs', 'requested_images')
    
    # Drop enum type
    op.execute("DROP TYPE IF EXISTS articlestatus")
