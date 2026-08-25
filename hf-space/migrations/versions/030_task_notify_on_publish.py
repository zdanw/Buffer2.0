"""add scheduled_tasks.notify_on_publish

Revision ID: 030_task_notify_on_publish
Revises: 029_logo_in_images
Create Date: 2026-08-25

自动发布成功后是否发送通知邮件。
"""

from alembic import op
import sqlalchemy as sa

revision = "030_task_notify_on_publish"
down_revision = "029_logo_in_images"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("scheduled_tasks", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "notify_on_publish",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("scheduled_tasks", schema=None) as batch_op:
        batch_op.drop_column("notify_on_publish")
