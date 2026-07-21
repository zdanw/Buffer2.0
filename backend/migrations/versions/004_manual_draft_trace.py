"""add manual_task_drafts dimensions and image_prompts

Revision ID: 004_draft_trace
Revises: 003_exec_trace
Create Date: 2026-07-21

手动任务草稿增加维度信息与图像提示词（与图片一一对应），便于待发布页溯源。
"""

from alembic import op
import sqlalchemy as sa


revision = "004_draft_trace"
down_revision = "003_exec_trace"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("manual_task_drafts", sa.Column("dimensions", sa.JSON(), nullable=True))
    op.add_column("manual_task_drafts", sa.Column("image_prompts", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("manual_task_drafts", "image_prompts")
    op.drop_column("manual_task_drafts", "dimensions")
