"""Phase 1A additive schema: preferred refs, GenerationRun, GenerationArtifact.

Revision ID: 038_grounded_generation_foundation
Revises: 037_generate_task_progress
"""

import sqlalchemy as sa
from alembic import op

revision = "038_grounded_generation_foundation"
down_revision = "037_generate_task_progress"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "product_images",
        sa.Column("sort_index", sa.Integer(), nullable=True),
    )
    op.add_column(
        "product_images",
        sa.Column(
            "is_preferred",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.create_table(
        "generation_runs",
        sa.Column("run_id", sa.String(length=36), primary_key=True),
        sa.Column("owner_user_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=True),
        sa.Column("scheduled_task_id", sa.String(length=36), nullable=True),
        sa.Column("generate_task_id", sa.String(length=36), nullable=True),
        sa.Column("rollout_mode_at_start", sa.String(length=32), nullable=False),
        sa.Column("experiment_variant", sa.String(length=64), nullable=True),
        sa.Column("requested_pipeline_version", sa.String(length=64), nullable=False),
        sa.Column("executed_pipeline_version", sa.String(length=64), nullable=False),
        sa.Column("fallback_reason", sa.Text(), nullable=True),
        sa.Column("fallback_path", sa.String(length=64), nullable=True),
        sa.Column("image_prompt_pipeline", sa.String(length=32), nullable=True),
        sa.Column("compare_group_id", sa.String(length=36), nullable=True),
        sa.Column("reference_manifest", sa.JSON(), nullable=True),
        sa.Column("provider_type", sa.String(length=32), nullable=True),
        sa.Column("provider_id", sa.String(length=36), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("image_size", sa.String(length=32), nullable=True),
        sa.Column("image_provider_mode", sa.String(length=16), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("error_category", sa.String(length=64), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=True),
        sa.Column("credits_charged", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider_usage", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["users.user_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.product_id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["scheduled_task_id"], ["scheduled_tasks.task_id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["generate_task_id"], ["generate_tasks.task_id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_generation_runs_owner_created",
        "generation_runs",
        ["owner_user_id", "created_at"],
    )
    op.create_index(
        "ix_generation_runs_product_created",
        "generation_runs",
        ["product_id", "created_at"],
    )
    op.create_index(
        "ix_generation_runs_compare_group",
        "generation_runs",
        ["compare_group_id"],
    )
    op.create_index(
        "ix_generation_runs_experiment",
        "generation_runs",
        ["experiment_variant"],
    )
    op.create_index(
        "ix_generation_runs_generate_task",
        "generation_runs",
        ["generate_task_id"],
    )
    op.create_index(
        "ix_generation_runs_owner_user_id",
        "generation_runs",
        ["owner_user_id"],
    )
    op.create_index(
        "ix_generation_runs_workspace_id",
        "generation_runs",
        ["workspace_id"],
    )

    op.create_table(
        "generation_artifacts",
        sa.Column("artifact_id", sa.String(length=36), primary_key=True),
        sa.Column("owner_user_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=True),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_index", sa.Integer(), nullable=False),
        sa.Column("cdn_url", sa.String(length=500), nullable=False),
        sa.Column(
            "selected",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("persistence_warning", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["users.user_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["generation_runs.run_id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_generation_artifacts_run",
        "generation_artifacts",
        ["run_id"],
    )
    op.create_index(
        "ix_generation_artifacts_owner_user_id",
        "generation_artifacts",
        ["owner_user_id"],
    )
    op.create_index(
        "ix_generation_artifacts_workspace_id",
        "generation_artifacts",
        ["workspace_id"],
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                "CREATE UNIQUE INDEX uq_product_images_preferred_product "
                "ON product_images (product_id) "
                "WHERE is_preferred AND image_type = 'product'"
            )
        )
        op.execute(
            sa.text(
                "CREATE UNIQUE INDEX uq_product_images_preferred_scene "
                "ON product_images (product_id) "
                "WHERE is_preferred AND image_type = 'scene'"
            )
        )
        op.execute(sa.text('ALTER TABLE "generation_runs" ENABLE ROW LEVEL SECURITY'))
        op.execute(
            sa.text('ALTER TABLE "generation_artifacts" ENABLE ROW LEVEL SECURITY')
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text('ALTER TABLE "generation_artifacts" DISABLE ROW LEVEL SECURITY')
        )
        op.execute(sa.text('ALTER TABLE "generation_runs" DISABLE ROW LEVEL SECURITY'))
        op.execute(sa.text("DROP INDEX IF EXISTS uq_product_images_preferred_scene"))
        op.execute(sa.text("DROP INDEX IF EXISTS uq_product_images_preferred_product"))
    op.drop_table("generation_artifacts")
    op.drop_table("generation_runs")
    op.drop_column("product_images", "is_preferred")
    op.drop_column("product_images", "sort_index")
