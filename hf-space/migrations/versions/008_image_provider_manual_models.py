"""add manual_models to image_provider_configs

Revision ID: 008_manual_models
Revises: 007_image_providers
Create Date: 2026-07-23

Provider 可维护手动模型列表，避免为同 Key 重复建配置。
"""

from alembic import op
import sqlalchemy as sa


revision = "008_manual_models"
down_revision = "007_image_providers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "image_provider_configs",
        sa.Column("manual_models", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("image_provider_configs", "manual_models")
