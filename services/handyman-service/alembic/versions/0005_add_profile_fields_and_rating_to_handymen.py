"""add profile fields and rating to handymen

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
    op.add_column("handymen", sa.Column("phone", sa.String(), nullable=True))
    op.add_column("handymen", sa.Column("first_name", sa.String(), nullable=True))
    op.add_column("handymen", sa.Column("last_name", sa.String(), nullable=True))
    op.add_column("handymen", sa.Column("national_id", sa.String(), nullable=True))
    op.add_column("handymen", sa.Column("address_line", sa.String(), nullable=True))
    op.add_column("handymen", sa.Column("postal_code", sa.String(), nullable=True))
    op.add_column("handymen", sa.Column("city", sa.String(), nullable=True))
    op.add_column("handymen", sa.Column("country", sa.String(), nullable=True))
    op.add_column("handymen", sa.Column("avg_rating", sa.Float(), nullable=False, server_default="0"))
    op.add_column("handymen", sa.Column("rating_count", sa.Integer(), nullable=False, server_default="0"))


def downgrade():
    op.drop_column("handymen", "rating_count")
    op.drop_column("handymen", "avg_rating")
    op.drop_column("handymen", "country")
    op.drop_column("handymen", "city")
    op.drop_column("handymen", "postal_code")
    op.drop_column("handymen", "address_line")
    op.drop_column("handymen", "national_id")
    op.drop_column("handymen", "last_name")
    op.drop_column("handymen", "first_name")
    op.drop_column("handymen", "phone")