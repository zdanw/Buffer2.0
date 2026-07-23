"""add image provider configs and task model fields

Revision ID: 007_image_providers
Revises: 006_ref_images
Create Date: 2026-07-23

支持可配置图像生成 Provider（加密存 API Key），任务可绑定模型。
"""

from alembic import op
import sqlalchemy as sa


revision = "007_image_providers"
down_revision = "006_ref_images"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "image_provider_configs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("provider_type", sa.String(length=50), nullable=False),
        sa.Column("base_url", sa.String(length=512), nullable=False),
        sa.Column("api_key_encrypted", sa.Text(), nullable=False),
        sa.Column("supports_list_models", sa.Boolean(), nullable=True),
        sa.Column("default_model", sa.String(length=255), nullable=True),
        sa.Column("extra_headers", sa.JSON(), nullable=True),
        sa.Column("extra_params", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.add_column("scheduled_tasks", sa.Column("image_provider_id", sa.String(length=36), nullable=True))
    op.add_column("scheduled_tasks", sa.Column("image_model", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("scheduled_tasks", "image_model")
    op.drop_column("scheduled_tasks", "image_provider_id")
    op.drop_table("image_provider_configs")
