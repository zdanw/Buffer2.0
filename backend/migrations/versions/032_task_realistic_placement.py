"""add scheduled_tasks.realistic_placement

Revision ID: 032_task_realistic_placement
Revises: 031_calendar_platform_posts
Create Date: 2026-08-25

Mirror Studio realistic_placement toggle on scheduled tasks.
"""

from alembic import op
import sqlalchemy as sa

revision = "032_task_realistic_placement"
down_revision = "031_calendar_platform_posts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("scheduled_tasks", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "realistic_placement",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("scheduled_tasks", schema=None) as batch_op:
        batch_op.drop_column("realistic_placement")
