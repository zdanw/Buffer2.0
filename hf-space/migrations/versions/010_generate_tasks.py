"""add generate_tasks for durable async generation status

Revision ID: 010_generate_tasks
Revises: 009_compat_policies
Create Date: 2026-07-25
"""

from alembic import op
import sqlalchemy as sa


revision = "010_generate_tasks"
down_revision = "009_compat_policies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "generate_tasks",
        sa.Column("task_id", sa.String(length=36), primary_key=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("generate_tasks")
