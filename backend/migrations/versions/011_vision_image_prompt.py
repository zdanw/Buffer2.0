"""add use_vision_image_prompt on scheduled_tasks

Revision ID: 011_vision_image_prompt
Revises: 010_generate_tasks
Create Date: 2026-07-31
"""

from alembic import op
import sqlalchemy as sa


revision = "011_vision_image_prompt"
down_revision = "010_generate_tasks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scheduled_tasks",
        sa.Column(
            "use_vision_image_prompt",
            sa.Boolean(),
            nullable=True,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("scheduled_tasks", "use_vision_image_prompt")
