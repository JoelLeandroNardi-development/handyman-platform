from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "auth_users",
        sa.Column("is_email_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "auth_users",
        sa.Column("auth_provider", sa.String(length=20), nullable=False, server_default="local"),
    )
    op.add_column("auth_users", sa.Column("google_sub", sa.String(length=255), nullable=True))
    op.add_column("auth_users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint("uq_auth_users_google_sub", "auth_users", ["google_sub"])

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"], unique=False)
    op.create_unique_constraint("uq_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"])

    op.create_table(
        "email_verification_tokens",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_email_verification_tokens_user_id", "email_verification_tokens", ["user_id"], unique=False)
    op.create_unique_constraint("uq_email_verification_tokens_token_hash", "email_verification_tokens", ["token_hash"])


def downgrade():
    op.drop_constraint("uq_email_verification_tokens_token_hash", "email_verification_tokens", type_="unique")
    op.drop_index("ix_email_verification_tokens_user_id", table_name="email_verification_tokens")
    op.drop_table("email_verification_tokens")

    op.drop_constraint("uq_password_reset_tokens_token_hash", "password_reset_tokens", type_="unique")
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")

    op.drop_constraint("uq_auth_users_google_sub", "auth_users", type_="unique")
    op.drop_column("auth_users", "last_login_at")
    op.drop_column("auth_users", "google_sub")
    op.drop_column("auth_users", "auth_provider")
    op.drop_column("auth_users", "is_email_verified")
