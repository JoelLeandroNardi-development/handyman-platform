"""add skills catalog tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-10
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "skills_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_skills_categories_key", "skills_categories", ["key"], unique=True)

    op.create_table(
        "skills_catalog_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("category_key", sa.String(), nullable=False),
        sa.Column("skill_key", sa.String(), nullable=False),
        sa.Column("category_label", sa.String(), nullable=False),
        sa.Column("skill_label", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("category_key", "skill_key", name="uq_skill_category_skill"),
        sa.UniqueConstraint("skill_key", name="uq_skill_key_global"),
    )
    op.create_index("ix_skills_catalog_items_category_key", "skills_catalog_items", ["category_key"], unique=False)
    op.create_index("ix_skills_catalog_items_skill_key", "skills_catalog_items", ["skill_key"], unique=False)


def downgrade():
    op.drop_index("ix_skills_catalog_items_skill_key", table_name="skills_catalog_items")
    op.drop_index("ix_skills_catalog_items_category_key", table_name="skills_catalog_items")
    op.drop_table("skills_catalog_items")

    op.drop_index("ix_skills_categories_key", table_name="skills_categories")
    op.drop_table("skills_categories")