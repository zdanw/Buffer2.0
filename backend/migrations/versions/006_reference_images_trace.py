"""add reference product/scene images to drafts and executions

Revision ID: 006_ref_images
Revises: 005_ptype_category
Create Date: 2026-07-22

记录生成时使用的参考产品图与场景图，便于内容预览/待发布/发布日历溯源。
"""

from alembic import op
import sqlalchemy as sa


revision = "006_ref_images"
down_revision = "005_ptype_category"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("manual_task_drafts", sa.Column("reference_product_images", sa.JSON(), nullable=True))
    op.add_column("manual_task_drafts", sa.Column("reference_scene_images", sa.JSON(), nullable=True))
    op.add_column("task_executions", sa.Column("reference_product_images", sa.JSON(), nullable=True))
    op.add_column("task_executions", sa.Column("reference_scene_images", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("task_executions", "reference_scene_images")
    op.drop_column("task_executions", "reference_product_images")
    op.drop_column("manual_task_drafts", "reference_scene_images")
    op.drop_column("manual_task_drafts", "reference_product_images")
