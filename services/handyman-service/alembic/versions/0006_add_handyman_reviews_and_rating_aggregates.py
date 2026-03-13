"""add handyman reviews and rating aggregates

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-13
"""

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "handyman_reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("booking_id", sa.String(), nullable=False),
        sa.Column("handyman_email", sa.String(), nullable=False),
        sa.Column("user_email", sa.String(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("review_text", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_index("ix_handyman_reviews_booking_id", "handyman_reviews", ["booking_id"], unique=True)
    op.create_index("ix_handyman_reviews_handyman_email", "handyman_reviews", ["handyman_email"])
    op.create_index("ix_handyman_reviews_user_email", "handyman_reviews", ["user_email"])


def downgrade():
    op.drop_index("ix_handyman_reviews_user_email", table_name="handyman_reviews")
    op.drop_index("ix_handyman_reviews_handyman_email", table_name="handyman_reviews")
    op.drop_index("ix_handyman_reviews_booking_id", table_name="handyman_reviews")
    op.drop_table("handyman_reviews")

    op.drop_column("handymen", "rating_count")
    op.drop_column("handymen", "avg_rating")