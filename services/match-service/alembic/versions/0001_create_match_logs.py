from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "match_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_latitude", sa.Float(), nullable=False),
        sa.Column("user_longitude", sa.Float(), nullable=False),
        sa.Column("skill", sa.String(), nullable=False),
    )


def downgrade():
    op.drop_table("match_logs")
