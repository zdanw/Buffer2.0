"""add unique constraint on prompt dimension scope item_id

Revision ID: 016_dimension_scope_unique
Revises: 015_brand_logo_url
Create Date: 2026-08-14
"""

from alembic import op


revision = "016_dimension_scope_unique"
down_revision = "015_brand_logo_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM prompt_dimensions
        WHERE dimension_id NOT IN (
            SELECT MIN(dimension_id)
            FROM prompt_dimensions
            GROUP BY product_type, dimension_type, item_id
        )
        """
    )
    with op.batch_alter_table("prompt_dimensions", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            "uq_prompt_dimension_scope_item",
            ["product_type", "dimension_type", "item_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("prompt_dimensions", schema=None) as batch_op:
        batch_op.drop_constraint(
            "uq_prompt_dimension_scope_item",
            type_="unique",
        )
