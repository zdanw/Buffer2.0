"""add brands table and product.brand_id

Revision ID: 013_brands
Revises: 012_exec_product_id
Create Date: 2026-08-14
"""

from alembic import op
import sqlalchemy as sa


revision = "013_brands"
down_revision = "012_exec_product_id"
branch_labels = None
depends_on = None

GENERIC_BRAND_ID = "00000000-0000-0000-0000-000000000001"
BEBCARE_BRAND_ID = "00000000-0000-0000-0000-000000000002"


def upgrade() -> None:
    op.create_table(
        "brands",
        sa.Column("brand_id", sa.String(length=36), primary_key=True),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_generic", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("voice", sa.String(length=200), nullable=True),
        sa.Column("audience", sa.Text(), nullable=True),
        sa.Column("tone_keywords", sa.String(length=500), nullable=True),
        sa.Column("default_selling_points", sa.JSON(), nullable=True),
        sa.Column("default_hashtags", sa.JSON(), nullable=True),
        sa.Column("emoji_style", sa.String(length=32), nullable=True),
        sa.Column("words_to_avoid", sa.Text(), nullable=True),
        sa.Column("logo_font_rule", sa.Text(), nullable=True),
        sa.Column("vertical_pack", sa.String(length=64), nullable=True),
        sa.Column("default_product_type", sa.String(length=100), nullable=True),
        sa.Column("copy_system_prompt", sa.Text(), nullable=True),
        sa.Column("image_system_prompt", sa.Text(), nullable=True),
        sa.Column("vision_image_system_prompt", sa.Text(), nullable=True),
        sa.Column("vision_scene_system_prompt", sa.Text(), nullable=True),
        sa.Column("narrative_perspectives", sa.JSON(), nullable=True),
        sa.Column("writing_styles", sa.JSON(), nullable=True),
        sa.Column("copy_emoji_hints", sa.String(length=200), nullable=True),
        sa.Column("copy_example", sa.Text(), nullable=True),
        sa.Column("image_fallback_selling_points", sa.String(length=500), nullable=True),
        sa.Column("copy_fallback_selling_points", sa.JSON(), nullable=True),
        sa.Column("extra", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_brands_slug", "brands", ["slug"], unique=True)

    op.add_column("products", sa.Column("brand_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_products_brand_id",
        "products",
        "brands",
        ["brand_id"],
        ["brand_id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_products_brand_id", "products", type_="foreignkey")
    op.drop_column("products", "brand_id")
    op.drop_index("ix_brands_slug", table_name="brands")
    op.drop_table("brands")
