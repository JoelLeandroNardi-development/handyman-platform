"""add job_description to bookings

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-12
"""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("bookings", sa.Column("job_description", sa.String(), nullable=True))


def downgrade():
    op.drop_column("bookings", "job_description")