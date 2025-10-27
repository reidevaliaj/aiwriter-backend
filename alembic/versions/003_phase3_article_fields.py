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
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # 0) Ensure the enum exists only once
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'articlestatus') THEN
            CREATE TYPE articlestatus AS ENUM ('draft', 'ready', 'failed');
        END IF;
    END$$;
    """)

    status_enum = postgresql.ENUM(
        'draft', 'ready', 'failed', name='articlestatus', create_type=False
    )

    # 1) Create articles table if missing; otherwise skip
    if not insp.has_table('articles'):
        op.create_table(
            'articles',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('job_id', sa.Integer(), sa.ForeignKey('jobs.id'), nullable=False),
            sa.Column('license_id', sa.Integer(), sa.ForeignKey('licenses.id'), nullable=False),
            sa.Column('topic', sa.Text(), nullable=False),
            sa.Column('language', sa.String(), nullable=False, server_default='de'),
            sa.Column('outline_json', sa.JSON(), nullable=True),
            sa.Column('article_html', sa.Text(), nullable=True),
            sa.Column('meta_title', sa.String(length=160), nullable=True),
            sa.Column('meta_description', sa.String(length=180), nullable=True),
            sa.Column('faq_json', sa.JSON(), nullable=True),
            sa.Column('schema_json', sa.JSON(), nullable=True),
            sa.Column('image_urls_json', sa.JSON(), nullable=True, server_default=sa.text("'[]'::json")),
            sa.Column('tokens_input', sa.Integer(), nullable=True),
            sa.Column('tokens_output', sa.Integer(), nullable=True),
            sa.Column('image_cost_cents', sa.Integer(), nullable=True, server_default=sa.text("0")),
            sa.Column('status', status_enum, nullable=False, server_default='draft'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        )
    # else: table exists; we won't try to recreate it

    # 2) Ensure indexes exist (Postgres supports IF NOT EXISTS)
    op.execute("CREATE INDEX IF NOT EXISTS ix_articles_job_id ON articles (job_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_articles_license_id ON articles (license_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_articles_created_at ON articles (created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_articles_license_created ON articles (license_id, created_at)")

    # 3) Update jobs table — add columns with safe defaults if missing, then backfill
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS requested_images INTEGER")
    op.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS language VARCHAR")

    # Set server defaults (only if they are currently NULL on existing rows)
    op.execute("UPDATE jobs SET requested_images = 0 WHERE requested_images IS NULL")
    op.execute("UPDATE jobs SET language = 'de' WHERE language IS NULL")

    # Optionally enforce not nulls & remove server defaults after backfill, if desired:
    # op.execute(\"ALTER TABLE jobs ALTER COLUMN requested_images SET NOT NULL\")
    # op.execute(\"ALTER TABLE jobs ALTER COLUMN language SET NOT NULL\")


def downgrade() -> None:
    # Drop indexes (IF EXISTS for safety)
    op.execute("DROP INDEX IF EXISTS ix_articles_license_created")
    op.execute("DROP INDEX IF EXISTS ix_articles_created_at")
    op.execute("DROP INDEX IF EXISTS ix_articles_license_id")
    op.execute("DROP INDEX IF EXISTS ix_articles_job_id")

    # Drop articles table (IF EXISTS to be safe)
    op.execute("DROP TABLE IF EXISTS articles")

    # Remove columns from jobs table (IF EXISTS)
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS language")
    op.execute("ALTER TABLE jobs DROP COLUMN IF EXISTS requested_images")

    # We do NOT drop the enum type automatically; it might be used elsewhere.
    # If you are sure it's unused, you could uncomment:
    # op.execute(\"DROP TYPE IF EXISTS articlestatus\")
