"""Phase 2A additive: offering type and deterministic ProductImage metadata.

Revision ID: 040_deterministic_asset_metadata
Revises: 039_generation_plan
"""

import sqlalchemy as sa
from alembic import op

revision = "040_deterministic_asset_metadata"
down_revision = "039_generation_plan"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column(
            "offering_type",
            sa.String(length=32),
            nullable=False,
            server_default="unknown",
        ),
    )
    op.add_column(
        "product_images",
        sa.Column("content_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "product_images",
        sa.Column("detected_mime_type", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "product_images",
        sa.Column("has_alpha", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "product_images",
        sa.Column("exif_orientation", sa.Integer(), nullable=True),
    )
    op.add_column(
        "product_images",
        sa.Column("analysis_status", sa.String(length=24), nullable=True),
    )
    op.add_column(
        "product_images",
        sa.Column("deterministic_metadata_version", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "product_images",
        sa.Column("deterministic_metadata_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "product_images",
        sa.Column("near_duplicate_of_image_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "product_images",
        sa.Column("basic_quality_json", sa.JSON(), nullable=True),
    )
    op.create_index(
        "ix_product_images_content_hash", "product_images", ["content_hash"]
    )
    op.create_index(
        "ix_product_images_analysis_status", "product_images", ["analysis_status"]
    )
    op.create_index(
        "ix_product_images_lazy_status_version",
        "product_images",
        ["analysis_status", "deterministic_metadata_version"],
    )
    with op.batch_alter_table("product_images") as batch_op:
        batch_op.create_foreign_key(
            "fk_product_images_near_duplicate",
            "product_images",
            ["near_duplicate_of_image_id"],
            ["image_id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("product_images") as batch_op:
        batch_op.drop_constraint(
            "fk_product_images_near_duplicate", type_="foreignkey"
        )
    op.drop_index("ix_product_images_lazy_status_version", table_name="product_images")
    op.drop_index("ix_product_images_analysis_status", table_name="product_images")
    op.drop_index("ix_product_images_content_hash", table_name="product_images")
    op.drop_column("product_images", "basic_quality_json")
    op.drop_column("product_images", "near_duplicate_of_image_id")
    op.drop_column("product_images", "deterministic_metadata_at")
    op.drop_column("product_images", "deterministic_metadata_version")
    op.drop_column("product_images", "analysis_status")
    op.drop_column("product_images", "exif_orientation")
    op.drop_column("product_images", "has_alpha")
    op.drop_column("product_images", "detected_mime_type")
    op.drop_column("product_images", "content_hash")
    op.drop_column("products", "offering_type")
