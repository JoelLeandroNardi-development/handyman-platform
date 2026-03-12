"""add profile fields to users

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-12
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("phone", sa.String(), nullable=True))
    op.add_column("users", sa.Column("first_name", sa.String(), nullable=True))
    op.add_column("users", sa.Column("last_name", sa.String(), nullable=True))
    op.add_column("users", sa.Column("national_id", sa.String(), nullable=True))
    op.add_column("users", sa.Column("address_line", sa.String(), nullable=True))
    op.add_column("users", sa.Column("postal_code", sa.String(), nullable=True))
    op.add_column("users", sa.Column("city", sa.String(), nullable=True))
    op.add_column("users", sa.Column("country", sa.String(), nullable=True))


def downgrade():
    op.drop_column("users", "country")
    op.drop_column("users", "city")
    op.drop_column("users", "postal_code")
    op.drop_column("users", "address_line")
    op.drop_column("users", "national_id")
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
    op.drop_column("users", "phone")