"""Add callback_url to sites table

Revision ID: 002
Revises: 001
Create Date: 2024-10-25 22:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add callback_url column to sites table
    op.add_column('sites', sa.Column('callback_url', sa.String(), nullable=True))


def downgrade() -> None:
    # Remove callback_url column from sites table
    op.drop_column('sites', 'callback_url')
