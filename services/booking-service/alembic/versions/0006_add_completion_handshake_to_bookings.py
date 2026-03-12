"""add completion handshake to bookings

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-12
"""

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "bookings",
        sa.Column("completed_by_user", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "bookings",
        sa.Column("completed_by_handyman", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "bookings",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "bookings",
        sa.Column("completion_rejected_by_handyman", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "bookings",
        sa.Column("completion_rejection_reason", sa.String(), nullable=True),
    )


def downgrade():
    op.drop_column("bookings", "completion_rejection_reason")
    op.drop_column("bookings", "completion_rejected_by_handyman")
    op.drop_column("bookings", "completed_at")
    op.drop_column("bookings", "completed_by_handyman")
    op.drop_column("bookings", "completed_by_user")