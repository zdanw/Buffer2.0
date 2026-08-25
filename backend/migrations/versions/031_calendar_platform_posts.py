"""task_executions.platform_posts, draft platform_posts, calendar index

Revision ID: 031_calendar_platform_posts
Revises: 030_task_notify_on_publish
Create Date: 2026-08-25

Persist outbound post links at publish time; index executions by owner + created_at
for month-scoped calendar queries.
"""

from alembic import op
import sqlalchemy as sa

revision = "031_calendar_platform_posts"
down_revision = "030_task_notify_on_publish"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("task_executions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("platform_posts", sa.JSON(), nullable=True))

    with op.batch_alter_table("manual_task_drafts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("platform_posts", sa.JSON(), nullable=True))

    op.create_index(
        "ix_task_executions_owner_created_at",
        "task_executions",
        ["owner_user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_task_executions_owner_created_at", table_name="task_executions")

    with op.batch_alter_table("manual_task_drafts", schema=None) as batch_op:
        batch_op.drop_column("platform_posts")

    with op.batch_alter_table("task_executions", schema=None) as batch_op:
        batch_op.drop_column("platform_posts")
