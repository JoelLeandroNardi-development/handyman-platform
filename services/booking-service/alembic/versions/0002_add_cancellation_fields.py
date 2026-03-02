"""add cancellation fields

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-02
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("bookings", sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("bookings", sa.Column("cancellation_reason", sa.String(), nullable=True))


def downgrade():
    op.drop_column("bookings", "cancellation_reason")
    op.drop_column("bookings", "canceled_at")