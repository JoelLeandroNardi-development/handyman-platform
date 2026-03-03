"""add users.created_at

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    # Optional: if you frequently sort/filter by created_at
    # op.create_index("ix_users_created_at", "users", ["created_at"])


def downgrade():
    # Optional: if you created it above
    # op.drop_index("ix_users_created_at", table_name="users")
    op.drop_column("users", "created_at")