"""Phase 2B additive: cached semantic product image analyses.

Revision ID: 041_product_image_analyses
Revises: 040_deterministic_asset_metadata
"""

import sqlalchemy as sa
from alembic import op

revision = "041_product_image_analyses"
down_revision = "040_deterministic_asset_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_image_analyses",
        sa.Column("analysis_id", sa.String(length=36), primary_key=True),
        sa.Column("owner_user_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=True),
        sa.Column("product_image_id", sa.String(length=36), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("model_version", sa.String(length=128), nullable=False),
        sa.Column("offering_context_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("normalized_result", sa.JSON(), nullable=True),
        sa.Column("raw_response", sa.Text(), nullable=True),
        sa.Column("usage", sa.JSON(), nullable=True),
        sa.Column("error_category", sa.String(length=64), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("analyzed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["users.user_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["product_image_id"],
            ["product_images.image_id"],
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "owner_user_id",
            "content_hash",
            "schema_version",
            "model_version",
            "offering_context_version",
            name="uq_product_image_analyses_cache_key",
        ),
    )
    op.create_index(
        "ix_product_image_analyses_image",
        "product_image_analyses",
        ["product_image_id"],
    )
    op.create_index(
        "ix_product_image_analyses_owner",
        "product_image_analyses",
        ["owner_user_id"],
    )
    op.create_index(
        "ix_product_image_analyses_status",
        "product_image_analyses",
        ["status"],
    )
    op.create_index(
        "ix_product_image_analyses_cache_identity",
        "product_image_analyses",
        [
            "content_hash",
            "schema_version",
            "model_version",
            "offering_context_version",
        ],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_product_image_analyses_cache_identity",
        table_name="product_image_analyses",
    )
    op.drop_index("ix_product_image_analyses_status", table_name="product_image_analyses")
    op.drop_index("ix_product_image_analyses_owner", table_name="product_image_analyses")
    op.drop_index("ix_product_image_analyses_image", table_name="product_image_analyses")
    op.drop_table("product_image_analyses")
