"""add nullable owner_user_id and workspace_id on tenant tables

Revision ID: 021_owner_workspace
Revises: 020_buffer_account_unique
Create Date: 2026-08-19
"""

from alembic import op
import sqlalchemy as sa


revision = "021_owner_workspace"
down_revision = "020_buffer_account_unique"
branch_labels = None
depends_on = None

OWNER_TABLES = (
    "brands",
    "products",
    "scheduled_tasks",
    "task_executions",
    "manual_task_drafts",
    "publish_records",
    "generate_tasks",
    "image_provider_configs",
    "buffer_accounts",
)


def upgrade() -> None:
    # SQLite cannot ALTER TABLE freely; batch copy-and-move (env.py render_as_batch).
    for table in OWNER_TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("owner_user_id", sa.String(length=36), nullable=True)
            )
            batch_op.add_column(
                sa.Column("workspace_id", sa.String(length=36), nullable=True)
            )


def downgrade() -> None:
    for table in reversed(OWNER_TABLES):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column("workspace_id")
            batch_op.drop_column("owner_user_id")
