"""initial schema

Revision ID: 001_initial
Revises:
Create Date: 2026-07-20

本地 SQLite 与生产 Supabase(PostgreSQL) 共用此基线迁移。
"""

from alembic import op
import sqlalchemy as sa


revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.String(length=36), primary_key=True),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=100), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("is_admin", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "products",
        sa.Column("product_id", sa.String(length=36), primary_key=True),
        sa.Column("product_name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("selling_points", sa.String(length=500), nullable=True),
        sa.Column("brand_voice", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "product_images",
        sa.Column("image_id", sa.String(length=36), primary_key=True),
        sa.Column("product_id", sa.String(length=36), nullable=True),
        sa.Column("cdn_url", sa.String(length=500), nullable=False),
        sa.Column("phash", sa.String(length=64), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("image_type", sa.String(length=20), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["product_id"], ["products.product_id"], ondelete="CASCADE"),
    )

    op.create_table(
        "scheduled_tasks",
        sa.Column("task_id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("cron", sa.String(length=100), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=True),
        sa.Column("target_categories", sa.JSON(), nullable=True),
        sa.Column("target_products", sa.JSON(), nullable=True),
        sa.Column("platforms", sa.JSON(), nullable=True),
        sa.Column("reference_image_count", sa.Integer(), nullable=True),
        sa.Column("run_count_per_execution", sa.Integer(), nullable=True),
        sa.Column("generate_image_count", sa.Integer(), nullable=True),
        sa.Column("generate_copy_count", sa.Integer(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=True),
        sa.Column("use_scene_reference", sa.Boolean(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("next_run_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "task_executions",
        sa.Column("execution_id", sa.String(length=36), primary_key=True),
        sa.Column("task_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("generated_images", sa.JSON(), nullable=True),
        sa.Column("published_platforms", sa.JSON(), nullable=True),
        sa.Column("copywriting", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["scheduled_tasks.task_id"], ondelete="CASCADE"),
    )

    op.create_table(
        "manual_task_drafts",
        sa.Column("draft_id", sa.String(length=36), primary_key=True),
        sa.Column("task_id", sa.String(length=36), nullable=True),
        sa.Column("product_id", sa.String(length=36), nullable=True),
        sa.Column("images", sa.JSON(), nullable=True),
        sa.Column("copywritings", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("selected_image", sa.Text(), nullable=True),
        sa.Column("selected_copy", sa.Text(), nullable=True),
        sa.Column("published_platforms", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["scheduled_tasks.task_id"], ondelete="CASCADE"),
    )

    op.create_table(
        "publish_records",
        sa.Column("publish_id", sa.String(length=36), primary_key=True),
        sa.Column("task_id", sa.String(length=36), nullable=True),
        sa.Column("product_id", sa.String(length=36), nullable=True),
        sa.Column("platform", sa.String(length=50), nullable=True),
        sa.Column("content", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("buffer_id", sa.String(length=255), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "operation_logs",
        sa.Column("log_id", sa.String(length=36), primary_key=True),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("context", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "prompt_dimensions",
        sa.Column("dimension_id", sa.String(length=36), primary_key=True),
        sa.Column("product_type", sa.String(length=100), nullable=False),
        sa.Column("dimension_type", sa.String(length=50), nullable=False),
        sa.Column("item_id", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("time", sa.String(length=50), nullable=True),
        sa.Column("lighting", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_prompt_dimensions_product_type", "prompt_dimensions", ["product_type"])
    op.create_index("ix_prompt_dimensions_dimension_type", "prompt_dimensions", ["dimension_type"])
    op.create_index("ix_prompt_dimensions_item_id", "prompt_dimensions", ["item_id"])

    op.create_table(
        "prompt_dimension_compatibilities",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("dimension_id", sa.String(length=36), nullable=True),
        sa.Column("source_dimension_type", sa.String(length=50), nullable=False),
        sa.Column("target_dimension_type", sa.String(length=50), nullable=False),
        sa.Column("target_item_id", sa.String(length=100), nullable=False),
        sa.Column("relation_type", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["dimension_id"], ["prompt_dimensions.dimension_id"], ondelete="CASCADE"),
    )

    op.create_table(
        "product_dimensions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("product_id", sa.String(length=36), nullable=True),
        sa.Column("dimension_id", sa.String(length=36), nullable=True),
        sa.Column("dimension_type", sa.String(length=50), nullable=False),
        sa.Column("item_id", sa.String(length=100), nullable=True),
        sa.Column("name", sa.String(length=500), nullable=True),
        sa.Column("time", sa.String(length=50), nullable=True),
        sa.Column("lighting", sa.JSON(), nullable=True),
        sa.Column("is_custom", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["product_id"], ["products.product_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["dimension_id"], ["prompt_dimensions.dimension_id"], ondelete="SET NULL"),
    )


def downgrade() -> None:
    op.drop_table("product_dimensions")
    op.drop_table("prompt_dimension_compatibilities")
    op.drop_index("ix_prompt_dimensions_item_id", table_name="prompt_dimensions")
    op.drop_index("ix_prompt_dimensions_dimension_type", table_name="prompt_dimensions")
    op.drop_index("ix_prompt_dimensions_product_type", table_name="prompt_dimensions")
    op.drop_table("prompt_dimensions")
    op.drop_table("operation_logs")
    op.drop_table("publish_records")
    op.drop_table("manual_task_drafts")
    op.drop_table("task_executions")
    op.drop_table("scheduled_tasks")
    op.drop_table("product_images")
    op.drop_table("products")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
