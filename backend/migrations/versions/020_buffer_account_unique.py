"""one brand per buffer account (exclusive)

Revision ID: 020_buffer_account_unique
Revises: 019_task_image_size
Create Date: 2026-08-18
"""

from alembic import op


revision = "020_buffer_account_unique"
down_revision = "019_task_image_size"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE brands
        SET buffer_account_id = NULL
        WHERE brand_id IN (
            SELECT brand_id FROM (
                SELECT brand_id,
                       ROW_NUMBER() OVER (
                           PARTITION BY buffer_account_id
                           ORDER BY brand_id
                       ) AS rn
                FROM brands
                WHERE buffer_account_id IS NOT NULL
            ) ranked
            WHERE rn > 1
        )
        """
    )
    op.drop_index("ix_brands_buffer_account_id", table_name="brands")
    op.create_index(
        "uq_brands_buffer_account_id",
        "brands",
        ["buffer_account_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_brands_buffer_account_id", table_name="brands")
    op.create_index("ix_brands_buffer_account_id", "brands", ["buffer_account_id"])
