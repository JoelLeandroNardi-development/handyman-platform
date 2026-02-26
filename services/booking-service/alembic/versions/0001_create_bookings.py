from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("booking_id", sa.String(), nullable=False),
        sa.Column("user_email", sa.String(), nullable=False),
        sa.Column("handyman_email", sa.String(), nullable=False),
        sa.Column("desired_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("desired_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("failure_reason", sa.String(), nullable=True),
    )
    op.create_index("ix_bookings_booking_id", "bookings", ["booking_id"], unique=True)
    op.create_index("ix_bookings_user_email", "bookings", ["user_email"], unique=False)
    op.create_index("ix_bookings_handyman_email", "bookings", ["handyman_email"], unique=False)
    op.create_index("ix_bookings_status", "bookings", ["status"], unique=False)

def downgrade():
    op.drop_index("ix_bookings_status", table_name="bookings")
    op.drop_index("ix_bookings_handyman_email", table_name="bookings")
    op.drop_index("ix_bookings_user_email", table_name="bookings")
    op.drop_index("ix_bookings_booking_id", table_name="bookings")
    op.drop_table("bookings")