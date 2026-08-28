"""Add progress and stage columns to generate_tasks.

Revision ID: 037_generate_task_progress
Revises: 036_clear_brand_vision
"""

import sqlalchemy as sa
from alembic import op

revision = "037_generate_task_progress"
down_revision = "036_clear_brand_vision"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "generate_tasks",
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "generate_tasks",
        sa.Column("stage", sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("generate_tasks", "stage")
    op.drop_column("generate_tasks", "progress")
