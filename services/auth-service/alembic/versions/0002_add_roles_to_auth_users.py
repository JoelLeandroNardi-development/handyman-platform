from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    # Add roles column (nullable first for existing rows)
    op.add_column("auth_users", sa.Column("roles", sa.JSON(), nullable=True))

    # Backfill existing rows
    op.execute("UPDATE auth_users SET roles = '[\"user\"]' WHERE roles IS NULL")

    # Enforce NOT NULL
    op.alter_column("auth_users", "roles", nullable=False)


def downgrade():
    op.drop_column("auth_users", "roles")
