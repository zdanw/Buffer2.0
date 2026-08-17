"""add scheduled_tasks.image_size

Revision ID: 019_task_image_size
Revises: 018_brand_voice_text
Create Date: 2026-08-17

可选图像输出尺寸（如 2048x2048），用于定时任务与比例选择。
"""

from alembic import op
import sqlalchemy as sa


revision = "019_task_image_size"
down_revision = "018_brand_voice_text"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("scheduled_tasks", schema=None) as batch_op:
        batch_op.add_column(sa.Column("image_size", sa.String(length=32), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("scheduled_tasks", schema=None) as batch_op:
        batch_op.drop_column("image_size")
