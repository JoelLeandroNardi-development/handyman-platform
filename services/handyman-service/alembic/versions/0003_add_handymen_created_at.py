"""add handymen.created_at

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
        "handymen",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    # Optional (only if you plan to sort/filter by created_at a lot):
    # op.create_index("ix_handymen_created_at", "handymen", ["created_at"])


def downgrade():
    # Optional:
    # op.drop_index("ix_handymen_created_at", table_name="handymen")
    op.drop_column("handymen", "created_at")