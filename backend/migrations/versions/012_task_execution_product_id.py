"""add product_id on task_executions for per-product prompt history

Revision ID: 012_exec_product_id
Revises: 011_vision_image_prompt
Create Date: 2026-08-03
"""

from alembic import op
import sqlalchemy as sa


revision = "012_exec_product_id"
down_revision = "011_vision_image_prompt"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "task_executions",
        sa.Column("product_id", sa.String(length=36), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("task_executions", "product_id")
