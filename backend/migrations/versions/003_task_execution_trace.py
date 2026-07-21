"""add task_executions dimensions and image_prompt

Revision ID: 003_exec_trace
Revises: 002_dim_enabled
Create Date: 2026-07-21

任务执行记录增加维度信息与图像提示词，便于发布日历溯源。
"""

from alembic import op
import sqlalchemy as sa


revision = "003_exec_trace"
down_revision = "002_dim_enabled"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("task_executions", sa.Column("dimensions", sa.JSON(), nullable=True))
    op.add_column("task_executions", sa.Column("image_prompt", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("task_executions", "image_prompt")
    op.drop_column("task_executions", "dimensions")
