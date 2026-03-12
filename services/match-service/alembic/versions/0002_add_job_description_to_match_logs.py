"""add job_description to match_logs

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-12
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("match_logs", sa.Column("job_description", sa.String(), nullable=True))


def downgrade():
    op.drop_column("match_logs", "job_description")