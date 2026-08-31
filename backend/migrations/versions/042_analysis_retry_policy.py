"""Phase 2B additive retry columns on product_image_analyses.

Revision ID: 042_analysis_retry_policy
Revises: 041_product_image_analyses
"""

import sqlalchemy as sa
from alembic import op

revision = "042_analysis_retry_policy"
down_revision = "041_product_image_analyses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "product_image_analyses",
        sa.Column("failure_type", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "product_image_analyses",
        sa.Column("next_retry_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "product_image_analyses",
        sa.Column("last_attempt_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_product_image_analyses_next_retry_at",
        "product_image_analyses",
        ["next_retry_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_product_image_analyses_next_retry_at",
        table_name="product_image_analyses",
    )
    op.drop_column("product_image_analyses", "last_attempt_at")
    op.drop_column("product_image_analyses", "next_retry_at")
    op.drop_column("product_image_analyses", "failure_type")
