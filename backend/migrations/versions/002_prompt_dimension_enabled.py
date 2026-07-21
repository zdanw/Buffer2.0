"""add prompt_dimensions.enabled

Revision ID: 002_dim_enabled
Revises: 001_initial
Create Date: 2026-07-21

为提示词维度增加启用开关；禁用后不参与生成与兼容选取。
"""

from alembic import op
import sqlalchemy as sa


revision = "002_dim_enabled"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "prompt_dimensions",
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("prompt_dimensions", "enabled")
