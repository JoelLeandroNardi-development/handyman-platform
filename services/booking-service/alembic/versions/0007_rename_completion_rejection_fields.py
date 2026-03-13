"""rename completion rejection fields to generic rejection fields

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-13
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "bookings",
        "completion_rejected_by_handyman",
        new_column_name="rejected_by_handyman",
    )
    op.alter_column(
        "bookings",
        "completion_rejection_reason",
        new_column_name="rejection_reason",
    )


def downgrade():
    op.alter_column(
        "bookings",
        "rejection_reason",
        new_column_name="completion_rejection_reason",
    )
    op.alter_column(
        "bookings",
        "rejected_by_handyman",
        new_column_name="completion_rejected_by_handyman",
    )